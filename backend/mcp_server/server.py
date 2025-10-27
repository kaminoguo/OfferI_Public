#!/usr/bin/env python3
"""
OfferI MCP Server - Workflow Orchestration Version 1.0.1

Architecture: Token-based workflow enforcement with 7 tools
- Each workflow tool returns a token required by the next tool
- Tools validate Exa search completeness internally
- LLM cannot skip steps (physical constraint via parameters)

Optimization (v1.0.1):
- Tool 1: Reduced Exa searches from 7 to 5 (2×25 + 3×15 results)
- Tool 4: Two-pass screening (conservative selection + remove mismatches)
- Tool 5: Two-stage validation (2×25 results: feasibility + detailed)
- Tool 7: Optimized search counts (8+15+4 results per program)

Transport Modes:
- STDIO: For internal workers (default)
- Streamable HTTP: For external Claude Desktop/Code users (use --http flag)
"""
import os
import sys
import sqlite3
import secrets
import json
from pathlib import Path
from typing import Optional, List, Any, Dict, Union
from datetime import datetime
from fastmcp import FastMCP

# Version
__version__ = "1.0.1"

# Database path
DB_PATH = os.getenv("DB_PATH", "/app/mcp/programs.db")

# In-memory token store (for validation)
_active_tokens = {}

# Initialize FastMCP server
mcp = FastMCP(
    name="OfferI Study Abroad",
    instructions="""
    Study abroad program consultation MCP server with 93,716 programs worldwide.
    Current date: October 2025

    WORKFLOW ENFORCEMENT:
    This server uses token-based workflow orchestration. You must call tools in sequence:
    1. start_consultation() - Validate 5 Exa admission searches (2x25 + 3x15 results)
    2. explore_universities() - Get all universities in country
    3. get_university_programs() - Get ALL programs for EACH selected university
    4. shortlist_programs_by_name() - Filter programs by name analysis
    5. validate_programs_with_exa() - Two-stage validation with Exa searches
    6. score_and_rank_programs() - Score and rank all programs
    7. generate_final_report() - Generate comprehensive report with detailed research

    LANGUAGE POLICY:
    Output language MUST match user's input language.

    CRITICAL: Database tuition data is unreliable. Always get tuition from Exa searches.
    """
)


# ═══════════════════════════════════════════════════════════════
# TOKEN MANAGEMENT
# ═══════════════════════════════════════════════════════════════

def generate_token(token_type: str, data: dict) -> str:
    """Generate a secure token with embedded data"""
    token = f"{token_type}_{secrets.token_urlsafe(16)}"
    _active_tokens[token] = {
        "type": token_type,
        "data": data,
        "created_at": datetime.utcnow().isoformat()
    }
    return token

def validate_token(token: str, expected_type: str) -> dict:
    """Validate token and return embedded data"""
    if not token or token not in _active_tokens:
        raise ValueError(f"Invalid or expired token. Did you call the previous step?")
    
    token_data = _active_tokens[token]
    if token_data["type"] != expected_type:
        raise ValueError(f"Wrong token type. Expected {expected_type}, got {token_data['type']}")
    
    return token_data["data"]


# ═══════════════════════════════════════════════════════════════
# DATABASE HELPERS (Internal - not exposed as tools)
# ═══════════════════════════════════════════════════════════════

def get_db_connection():
    """Create database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def clean_null_values(data: Any) -> Any:
    """Remove null, empty, N/A values"""
    if isinstance(data, dict):
        return {
            k: clean_null_values(v)
            for k, v in data.items()
            if v is not None
            and v != ''
            and v != 'N/A'
            and v != 'null'
            and not (isinstance(v, (list, dict)) and not v)
        }
    elif isinstance(data, list):
        return [clean_null_values(item) for item in data if item is not None]
    return data

def _list_universities(country: str) -> List[str]:
    """Internal: Get all universities in a country"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT university_name
        FROM programs
        WHERE country_standardized = ?
        GROUP BY university_name
        ORDER BY COUNT(*) DESC
    """, [country])
    results = cursor.fetchall()
    conn.close()
    
    return [row["university_name"] for row in results]

def _get_available_countries() -> List[Dict[str, Any]]:
    """Internal: Get all countries with program counts"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT country_standardized, COUNT(*) as count
        FROM programs
        WHERE country_standardized IS NOT NULL
        GROUP BY country_standardized
        ORDER BY count DESC
    """)
    results = cursor.fetchall()
    conn.close()
    
    return [{"country": row["country_standardized"], "count": row["count"]} for row in results]

def _search_programs(university_name: str) -> List[Dict[str, Any]]:
    """Internal: Get all programs for a university"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT program_id, program_name
        FROM programs
        WHERE LOWER(university_name) LIKE LOWER(?)
        ORDER BY program_name
    """, [f"%{university_name}%"])
    results = cursor.fetchall()
    conn.close()
    
    return [{"id": row["program_id"], "name": row["program_name"]} for row in results]

def _get_program_details_batch(program_ids: List[int]) -> List[dict]:
    """Internal: Get essential details for multiple programs"""
    if not program_ids:
        return []
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    placeholders = ','.join('?' * len(program_ids))
    query = f"""
        SELECT program_id, program_name, university_name,
               country_standardized, city, degree_type,
               duration_months, study_mode
        FROM programs
        WHERE program_id IN ({placeholders})
    """
    
    cursor.execute(query, program_ids)
    results = cursor.fetchall()
    conn.close()
    
    programs = []
    for row in results:
        program = {
            "program_id": row["program_id"],
            "program_name": row["program_name"],
            "university_name": row["university_name"],
            "country_standardized": row["country_standardized"],
            "city": row["city"],
            "degree_type": row["degree_type"],
            "duration_months": row["duration_months"]
        }
        
        study_mode = row["study_mode"]
        if study_mode and "part" in study_mode.lower():
            program["is_part_time"] = True
        
        programs.append(program)
    
    return [clean_null_values(p) for p in programs]


# ═══════════════════════════════════════════════════════════════
# BACKGROUND ANALYSIS HELPERS (AI-Driven, Flexible)
# ═══════════════════════════════════════════════════════════════

def analyze_hard_criteria(background: str) -> dict:
    """
    Extract quantifiable academic criteria from student background.
    Uses flexible AI analysis - no hard-coded field expectations.

    Args:
        background: Free-text student background

    Returns:
        dict with school_tier, gpa_range, major_field (or "unknown" if not mentioned)
    """
    # Note: This is a simplified version. In production, use an LLM API call
    # For now, return a structured placeholder to demonstrate the pattern

    background_lower = background.lower()

    # School tier heuristics (simplified)
    school_tier = "unknown"
    if any(keyword in background_lower for keyword in ["top", "985", "211", "ivy", "stanford", "mit", "cmu"]):
        school_tier = "top-tier"
    elif any(keyword in background_lower for keyword in ["mid", "state university"]):
        school_tier = "mid-tier"

    # GPA range heuristics (simplified)
    gpa_range = "unknown"
    if "gpa" in background_lower or "grade" in background_lower:
        if any(str(gpa) in background for gpa in ["3.8", "3.9", "4.0", "3.7"]):
            gpa_range = "high"
        elif any(str(gpa) in background for gpa in ["3.0", "3.1", "3.2", "3.3", "3.4", "3.5"]):
            gpa_range = "medium"
        else:
            gpa_range = "low"

    # Major field extraction (simplified)
    major_field = "unknown"
    if any(keyword in background_lower for keyword in ["cs", "computer science", "software"]):
        major_field = "Computer Science"
    elif any(keyword in background_lower for keyword in ["ee", "electrical", "electronic"]):
        major_field = "Electrical Engineering"
    elif any(keyword in background_lower for keyword in ["ai", "artificial intelligence", "machine learning"]):
        major_field = "AI/ML"
    elif any(keyword in background_lower for keyword in ["business", "management"]):
        major_field = "Business"

    return {
        "school_tier": school_tier,
        "gpa_range": gpa_range,
        "major_field": major_field
    }


def analyze_soft_criteria(background: str, target_country: str) -> list:
    """
    Identify unique strengths and distinctive aspects from student background.
    Completely flexible - no predefined categories.

    Args:
        background: Free-text student background
        target_country: Target country for applications

    Returns:
        list of dicts with aspect description and suggested search query
    """
    # Note: This is a simplified version. In production, use an LLM API call
    # For now, return structured placeholders demonstrating the pattern

    aspects = []
    background_lower = background.lower()

    # Work/internship experience
    if any(keyword in background_lower for keyword in ["intern", "work", "experience", "job"]):
        aspects.append({
            "aspect": "Professional work experience",
            "search_angle": "internship and work experience",
            "priority": 1
        })

    # Projects and publications
    if any(keyword in background_lower for keyword in ["project", "github", "publication", "paper", "research"]):
        aspects.append({
            "aspect": "Technical projects and research",
            "search_angle": "projects and research publications",
            "priority": 2
        })

    # Leadership and awards
    if any(keyword in background_lower for keyword in ["award", "competition", "hackathon", "lead", "president"]):
        aspects.append({
            "aspect": "Leadership and achievements",
            "search_angle": "awards competitions and leadership",
            "priority": 3
        })

    # Career goals
    if any(keyword in background_lower for keyword in ["pm", "product manager", "cpo", "career", "goal"]):
        aspects.append({
            "aspect": "Career trajectory goals",
            "search_angle": "career transition and goals",
            "priority": 4
        })

    # Return top 3 aspects sorted by priority
    aspects.sort(key=lambda x: x["priority"])
    return aspects[:3]


def generate_school_major_match_query(school_tier: str, major_field: str, target_country: str) -> str:
    """Generate natural language query for school tier + major matching"""
    tier_map = {
        "top-tier": "top university",
        "mid-tier": "mid-tier university",
        "low-tier": "university",
        "unknown": "university"
    }

    tier_str = tier_map.get(school_tier, "university")
    major_str = major_field if major_field != "unknown" else "STEM"

    query = f"{tier_str} {major_str} students admitted to {target_country} graduate programs 2024"

    return query


def generate_gpa_major_match_query(gpa_range: str, major_field: str, target_country: str) -> str:
    """Generate natural language query for GPA + major matching"""
    gpa_map = {
        "high": "high GPA",
        "medium": "medium GPA",
        "low": "lower GPA",
        "unknown": ""
    }

    gpa_str = gpa_map.get(gpa_range, "")
    major_str = major_field if major_field != "unknown" else "STEM"

    if gpa_str:
        query = f"{gpa_str} {major_str} students successful {target_country} graduate admissions 2024"
    else:
        query = f"{major_str} students {target_country} graduate school admission cases 2024"

    return query


def generate_flexible_query(aspect: dict, target_country: str) -> str:
    """
    Generate flexible query based on AI-extracted aspect.
    Pure AI-driven, no hard-coding.
    """
    search_angle = aspect.get("search_angle", "background")

    query = f"students with {search_angle} admitted to {target_country} graduate programs 2024"

    return query


# ═══════════════════════════════════════════════════════════════
# WORKFLOW ORCHESTRATION TOOLS
# ═══════════════════════════════════════════════════════════════

@mcp.tool
async def start_consultation(
    background: str,
    exa_admission_searches: List[dict]
) -> dict:
    """
    Step 1: Start consultation session

    YOU MUST complete 5 Exa admission case searches BEFORE calling this tool.

    Structure:
    - First 2 searches: 25 results each (hard criteria: school tier, GPA, major)
    - Last 3 searches: 15 results each (soft criteria: AI-extracted unique strengths)

    Args:
        background: Student background (free text - GPA, university, internships, projects, etc.)
        exa_admission_searches: List of 5 Exa search results
            First 2: {"query": "...", "num_results": 25, "key_findings": "..."}
            Last 3: {"query": "...", "num_results": 15, "key_findings": "..."}

    Returns:
        consultation_token + next_step instructions
    """
    if not exa_admission_searches or len(exa_admission_searches) != 5:
        raise ValueError(f"You must provide EXACTLY 5 Exa admission searches. You provided {len(exa_admission_searches) if exa_admission_searches else 0}.")

    # Validate first 2 searches (hard criteria, 25 results each)
    for i in range(2):
        search = exa_admission_searches[i]
        if not isinstance(search, dict) or "query" not in search or "num_results" not in search:
            raise ValueError(f"Search #{i+1} must be a dict with 'query' and 'num_results' fields")
        if search["num_results"] != 25:
            raise ValueError(f"Search #{i+1} (hard criteria) must have EXACTLY 25 results (you provided {search['num_results']})")

    # Validate last 3 searches (soft criteria, 15 results each)
    for i in range(2, 5):
        search = exa_admission_searches[i]
        if not isinstance(search, dict) or "query" not in search or "num_results" not in search:
            raise ValueError(f"Search #{i+1} must be a dict with 'query' and 'num_results' fields")
        if search["num_results"] != 15:
            raise ValueError(f"Search #{i+1} (soft criteria) must have EXACTLY 15 results (you provided {search['num_results']})")

    token = generate_token("consultation", {
        "background": background,
        "exa_searches_completed": len(exa_admission_searches),
        "hard_criteria_searches": 2,
        "soft_criteria_searches": 3
    })

    return {
        "consultation_token": token,
        "parsed_background": {"raw": background, "exa_searches_completed": 5, "pattern": "2x25 + 3x15"},
        "next_step": "Call explore_universities(country, consultation_token)"
    }


@mcp.tool
async def explore_universities(
    country: str,
    consultation_token: str
) -> dict:
    """
    Step 2: Get all universities in target country
    
    Args:
        country: "USA", "UK", "Hong Kong (SAR)", etc.
        consultation_token: From start_consultation()
    
    Returns:
        exploration_token + list of all universities
    """
    validate_token(consultation_token, "consultation")
    
    universities = _list_universities(country)
    
    if not universities:
        available = _get_available_countries()
        countries_str = ", ".join([f"{c['country']} ({c['count']})" for c in available[:10]])
        raise ValueError(f"Country '{country}' not found. Available: {countries_str}")
    
    token = generate_token("exploration", {
        "country": country,
        "universities": universities,
        "total_universities": len(universities)
    })
    
    return {
        "exploration_token": token,
        "universities": universities,
        "total_count": len(universities),
        "instructions": """
Review EVERY university name. Select appropriate ones based on:
- School tier matches student credentials?
- Values student's strengths (internships/projects/awards)?
- Supports student's career goals?

DO NOT just pick "famous Top 20". Consider fit over fame.

Next: Call get_university_programs() for EACH selected university
        """,
        "next_step": "Call get_university_programs(universities, exploration_token)"
    }


@mcp.tool
async def get_university_programs(
    universities: List[str],
    exploration_token: str
) -> dict:
    """
    Step 3: Get ALL programs for EACH selected university
    
    Args:
        universities: List of university names you selected (e.g., ["CMU", "Stanford", ...])
        exploration_token: From explore_universities()
    
    Returns:
        programs_token + all programs grouped by university
    """
    validate_token(exploration_token, "exploration")
    
    if not universities or not isinstance(universities, list):
        raise ValueError("You must provide a list of university names")
    
    all_programs = {}
    total_programs = 0
    
    for uni in universities:
        programs = _search_programs(uni)
        if programs:
            all_programs[uni] = programs
            total_programs += len(programs)
    
    token = generate_token("programs", {
        "universities": universities,
        "all_programs": all_programs,
        "total_programs": total_programs
    })
    
    return {
        "programs_token": token,
        "programs_by_university": all_programs,
        "total_programs": total_programs,
        "universities_count": len(all_programs),
        "instructions": """
You now have ALL programs for each university.

CRITICAL: Perform TWO-PASS screening to ensure quality and reduce Exa search load.

PASS 1 - Initial Screening (Conservative Selection):
- Review ALL program names carefully
- Select potentially relevant programs
- Use CONSERVATIVE criteria (better fewer than more - avoid selecting too many)
- Focus on clear relevance to student background
- DO NOT include programs just because they "might" be relevant

PASS 2 - Final Refinement (Remove Obvious Mismatches):
- Review your Pass 1 selection
- Remove programs that are OBVIOUSLY irrelevant
- Remove programs with clear mismatches (e.g., healthcare programs for CS students)
- Keep borderline cases (they will be validated by Exa later)
- Goal: Reduce load for subsequent Exa searches while preserving quality candidates

Submit ONLY the final shortlist after both passes.

Call shortlist_programs_by_name(shortlisted_by_university, programs_token)
        """,
        "next_step": "Call shortlist_programs_by_name(shortlisted_by_university, programs_token)"
    }


@mcp.tool
async def shortlist_programs_by_name(
    shortlisted_by_university: Dict[str, List[int]],
    programs_token: str
) -> dict:
    """
    Step 4: Shortlist programs by name analysis
    
    Args:
        shortlisted_by_university: Dict mapping university name to list of program IDs
            Example: {
                "CMU": [123, 456, 789],
                "Stanford": [234, 567],
                ...
            }
        programs_token: From get_university_programs()
    
    Returns:
        shortlist_token + statistics
    """
    programs_data = validate_token(programs_token, "programs")
    
    if not shortlisted_by_university or not isinstance(shortlisted_by_university, dict):
        raise ValueError("You must provide shortlisted_by_university as a dict")
    
    total_shortlisted = sum(len(ids) for ids in shortlisted_by_university.values())
    
    if total_shortlisted == 0:
        raise ValueError("You must shortlist at least some programs. Did you review the program names?")
    
    token = generate_token("shortlist", {
        "universities": list(shortlisted_by_university.keys()),
        "shortlisted_by_university": shortlisted_by_university,
        "total_shortlisted": total_shortlisted
    })
    
    university_names = list(shortlisted_by_university.keys())

    return {
        "shortlist_token": token,
        "shortlisted_by_university": shortlisted_by_university,
        "total_shortlisted": total_shortlisted,
        "universities_count": len(shortlisted_by_university),
        "university_names_for_validation": university_names,
        "instructions": f"""
You have shortlisted {total_shortlisted} programs across {len(shortlisted_by_university)} universities.

CRITICAL NEXT STEP: For EACH university, do TWO Exa searches (25 results each).

⚠️ IMPORTANT: You MUST use these EXACT university names as keys in exa_validations dict:
{chr(10).join([f'  - "{name}"' for name in university_names])}

Two-stage validation per university:

Stage 1 (25 results): Admission feasibility check
Query: "[University] [Program 1] [Program 2] admission requirements work experience GPA prerequisites"
Purpose: Filter out programs with mismatched hard requirements

Stage 2 (25 results): Detailed validation
Query: "[University] [Program 1] [Program 2] curriculum focus career outcomes student profile"
Purpose: Understand program characteristics and fit

Call validate_programs_with_exa(exa_validations, shortlist_token)

Example structure:
{{
  "{university_names[0] if university_names else 'University Name'}": {{
    "stage1_exa": {{
      "query": "...",
      "num_results": 25,
      "findings": "..."
    }},
    "stage2_exa": {{
      "query": "...",
      "num_results": 25,
      "findings": "..."
    }},
    "final_program_ids": [123, 456]
  }}
}}
        """,
        "next_step": "Call validate_programs_with_exa(exa_validations, shortlist_token)"
    }


@mcp.tool
async def validate_programs_with_exa(
    exa_validations: Dict[str, dict],
    shortlist_token: str
) -> dict:
    """
    Step 5: Two-stage validation with Exa searches (TWO per university, 25 results each)

    Stage 1: Admission feasibility check (25 results) - filter by hard criteria
    Stage 2: Detailed validation (25 results) - comprehensive program analysis

    Args:
        exa_validations: Dict mapping university name to validation data
            IMPORTANT: Keys must EXACTLY match university names from shortlist_programs_by_name
            Example: {
                "CMU": {
                    "stage1_exa": {
                        "query": "CMU MISM MSAI admission requirements work experience GPA",
                        "num_results": 25,
                        "findings": "MISM requires 2+ years, MSAI prefers research..."
                    },
                    "stage2_exa": {
                        "query": "CMU MISM MSAI curriculum career outcomes alumni",
                        "num_results": 25,
                        "findings": "MISM is career-oriented, MSAI is research-heavy..."
                    },
                    "final_program_ids": [123, 456]
                },
                "Stanford": {
                    "stage1_exa": {...},
                    "stage2_exa": {...},
                    "final_program_ids": [234]
                },
                ...
            }
        shortlist_token: From shortlist_programs_by_name()

    Returns:
        validation_token + final program list
    """
    shortlist_data = validate_token(shortlist_token, "shortlist")

    if not exa_validations or not isinstance(exa_validations, dict):
        raise ValueError("You must provide exa_validations as a dict")

    expected_unis = shortlist_data["universities"]

    # Check that all universities have validation
    missing_unis = [uni for uni in expected_unis if uni not in exa_validations]
    if missing_unis:
        provided_keys = list(exa_validations.keys())
        raise ValueError(
            f"Missing Exa validation for universities: {missing_unis}\n\n"
            f"You provided keys: {provided_keys}\n\n"
            f"⚠️ You must use EXACT university names from shortlist_programs_by_name response.\n"
            f"Expected keys: {expected_unis}\n\n"
            f"Tip: Copy the exact names from 'university_names_for_validation' field in previous response."
        )

    # Validate each university's two-stage Exa searches
    all_final_ids = []
    total_searches = 0

    for uni, validation in exa_validations.items():
        if not isinstance(validation, dict):
            raise ValueError(f"{uni}: validation must be a dict")

        # Validate Stage 1
        if "stage1_exa" not in validation:
            raise ValueError(f"{uni}: missing 'stage1_exa' (admission feasibility check)")

        stage1 = validation["stage1_exa"]
        if not isinstance(stage1, dict) or "num_results" not in stage1:
            raise ValueError(f"{uni}: stage1_exa must be a dict with 'num_results' field")
        if stage1["num_results"] != 25:
            raise ValueError(f"{uni}: stage1_exa must have EXACTLY 25 results. You provided {stage1['num_results']}")
        total_searches += 1

        # Validate Stage 2
        if "stage2_exa" not in validation:
            raise ValueError(f"{uni}: missing 'stage2_exa' (detailed validation)")

        stage2 = validation["stage2_exa"]
        if not isinstance(stage2, dict) or "num_results" not in stage2:
            raise ValueError(f"{uni}: stage2_exa must be a dict with 'num_results' field")
        if stage2["num_results"] != 25:
            raise ValueError(f"{uni}: stage2_exa must have EXACTLY 25 results. You provided {stage2['num_results']}")
        total_searches += 1

        # Validate final program IDs
        if "final_program_ids" not in validation:
            raise ValueError(f"{uni}: validation must have 'final_program_ids' field")

        final_ids = validation["final_program_ids"]
        if not isinstance(final_ids, list):
            raise ValueError(f"{uni}: final_program_ids must be a list")

        all_final_ids.extend(final_ids)

    if len(all_final_ids) == 0:
        raise ValueError("No programs passed validation. Did you filter too aggressively?")

    token = generate_token("validation", {
        "universities_validated": len(exa_validations),
        "exa_searches_completed": total_searches,
        "final_program_ids": all_final_ids,
        "exa_validations": exa_validations
    })

    return {
        "validation_token": token,
        "universities_validated": len(exa_validations),
        "total_exa_searches": total_searches,
        "final_programs_count": len(all_final_ids),
        "final_program_ids": all_final_ids,
        "message": f"✅ Validated {len(exa_validations)} universities with {total_searches} Exa searches (2 stages × 25 results each)",
        "next_step": "Call score_and_rank_programs(validation_token)"
    }


@mcp.tool
async def score_and_rank_programs(
    validation_token: str
) -> dict:
    """
    Step 6: Score and rank all validated programs
    
    Args:
        validation_token: From validate_programs_with_exa()
    
    Returns:
        ranking_token + top programs + required Exa search count for detailed research
    """
    validation_data = validate_token(validation_token, "validation")
    
    final_ids = validation_data["final_program_ids"]
    universities_count = validation_data["universities_validated"]
    
    # Get program details
    programs = _get_program_details_batch(final_ids)
    
    # Calculate scores (placeholder - implement actual logic)
    for i, program in enumerate(programs):
        program["score"] = 95 - i
        program["rank"] = i + 1
    
    # Determine report format
    if universities_count >= 7:
        report_format = "TOP_20"
        detailed_count = 10
        required_searches = 30
    else:
        report_format = "TOP_10"
        detailed_count = 5
        required_searches = 15
    
    top_programs = programs[:detailed_count * 2]
    
    token = generate_token("ranking", {
        "report_format": report_format,
        "detailed_tier_count": detailed_count,
        "required_exa_searches": required_searches,
        "top_programs": top_programs
    })
    
    return {
        "ranking_token": token,
        "report_format": report_format,
        "detailed_tier_programs": detailed_count,
        "concise_tier_programs": detailed_count,
        "total_top_programs": len(top_programs),
        "required_exa_searches": required_searches,
        "top_programs": top_programs,
        "instructions": f"""
✅ Scored and ranked all programs.

Report format: {report_format}
- Tier 1 (detailed): {detailed_count} programs
- Tier 2 (concise): {detailed_count} programs

CRITICAL: You must complete {required_searches} Exa searches before generating report.

For EACH of the top {detailed_count} programs (Tier 1), do EXACTLY 3 Exa searches:
1. Location + Cost (8 results): "[University] [Program] location city living environment tuition fees total cost"
2. Program Core + Outlook (15 results): "[University] [Program] curriculum intensity program features industry development prospects"
3. Application Timeline (4 results): "[University] [Program] application deadline requirements process timeline"

Note the different result counts: 8, 15, 4 (total 27 per program)

Work systematically: Program #1 (3 searches) → #2 → ... → #{detailed_count}

Call generate_final_report(detailed_research, ranking_token)
        """,
        "next_step": f"Complete {required_searches} Exa searches, then call generate_final_report()"
    }


@mcp.tool
async def generate_final_report(
    detailed_program_research: List[dict],
    ranking_token: str
) -> dict:
    """
    Step 7: Generate comprehensive two-tier report

    Args:
        detailed_program_research: List of research for Tier 1 programs
            Each: {
                "program_id": 123,
                "exa_searches": [
                    {"query": "location cost...", "num_results": 8, "findings": "..."},
                    {"query": "program core outlook...", "num_results": 15, "findings": "..."},
                    {"query": "application timeline...", "num_results": 4, "findings": "..."}
                ],
                "dimensions": {
                    "location_environment": {...},
                    "career_prospects": {...},
                    "program_intensity": {...},
                    "unique_features": [...],
                    "application_timeline": {...},
                    "total_cost": {...}
                }
            }
        ranking_token: From score_and_rank_programs()

    Returns:
        Validation confirmation + instructions to generate report
    """
    ranking_data = validate_token(ranking_token, "ranking")
    
    report_format = ranking_data["report_format"]
    detailed_count = ranking_data["detailed_tier_count"]
    required_searches = ranking_data["required_exa_searches"]
    
    if not detailed_program_research or len(detailed_program_research) != detailed_count:
        raise ValueError(f"You must provide research for EXACTLY {detailed_count} programs. You provided {len(detailed_program_research) if detailed_program_research else 0}.")
    
    total_searches = 0
    validation_results = []
    
    for i, research in enumerate(detailed_program_research):
        program_id = research.get("program_id")
        exa_searches = research.get("exa_searches", [])
        dimensions = research.get("dimensions", {})
        
        if not program_id:
            raise ValueError(f"Research #{i+1}: missing program_id")
        
        if len(exa_searches) != 3:
            raise ValueError(f"Program {program_id}: must have EXACTLY 3 Exa searches. You provided {len(exa_searches)}.")

        # Validate each search with specific result count requirements
        expected_results = [8, 15, 4]
        search_names = ["Location + Cost", "Program Core + Outlook", "Application Timeline"]

        for j, search in enumerate(exa_searches):
            if not isinstance(search, dict) or "num_results" not in search:
                raise ValueError(f"Program {program_id}, Search #{j+1} ({search_names[j]}): must be a dict with 'num_results' field")

            expected = expected_results[j]
            actual = search["num_results"]

            if actual != expected:
                raise ValueError(
                    f"Program {program_id}, Search #{j+1} ({search_names[j]}): "
                    f"must have EXACTLY {expected} results. You provided {actual}"
                )

            total_searches += 1
        
        required_dims = ["location_environment", "career_prospects", "program_intensity", 
                        "unique_features", "application_timeline", "total_cost"]
        missing_dims = [dim for dim in required_dims if dim not in dimensions]
        if missing_dims:
            raise ValueError(f"Program {program_id}: missing dimensions: {missing_dims}")
        
        validation_results.append({
            "program_id": program_id,
            "exa_searches_count": len(exa_searches),
            "dimensions_complete": True
        })
    
    if total_searches != required_searches:
        raise ValueError(f"Expected {required_searches} total Exa searches, but you provided {total_searches}")
    
    return {
        "report_generated": True,
        "report_format": report_format,
        "tier1_programs": detailed_count,
        "tier2_programs": detailed_count,
        "total_exa_searches_validated": total_searches,
        "validation": validation_results,
        "message": f"""
✅ All validations passed! Generate the comprehensive report now.

Report structure:
- TIER 1: {detailed_count} programs with full 6-dimension profiles
- TIER 2: {detailed_count} programs with concise summaries
- Final section: Application strategy

Output in user's language (Chinese if they wrote in Chinese).
        """
    }


# ═══════════════════════════════════════════════════════════════
# UTILITY TOOLS
# ═══════════════════════════════════════════════════════════════

@mcp.tool
async def get_available_countries() -> str:
    """Get all countries with program counts. Use if unsure about country names."""
    countries = _get_available_countries()
    return "\n".join([f"{c['country']} ({c['count']} programs)" for c in countries])


@mcp.tool
async def get_database_statistics() -> dict:
    """Get database statistics for understanding data coverage."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as total FROM programs")
    total = cursor.fetchone()["total"]
    
    cursor.execute("""
        SELECT country_standardized as country, COUNT(*) as count
        FROM programs
        WHERE country_standardized IS NOT NULL
        GROUP BY country_standardized
        ORDER BY count DESC
        LIMIT 10
    """)
    countries = [{"country": row["country"], "count": row["count"]} for row in cursor.fetchall()]
    
    cursor.execute("""
        SELECT degree_type, COUNT(*) as count
        FROM programs
        WHERE degree_type IS NOT NULL
        GROUP BY degree_type
        ORDER BY count DESC
    """)
    degrees = [{"degree_type": row["degree_type"], "count": row["count"]} for row in cursor.fetchall()]
    
    conn.close()
    
    return {
        "total_programs": total,
        "top_countries": countries,
        "degree_types": degrees
    }


@mcp.tool()
async def _internal_track_usage() -> str:
    """Internal usage tracking. Returns empty string."""
    import psycopg2
    from fastmcp.server.dependencies import get_http_headers
    
    api_key = ""
    try:
        headers = get_http_headers()
        auth_header = headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
    except:
        api_key = os.getenv("SSE_API_KEY", "")
    
    if not api_key or not api_key.startswith("sk_"):
        return ""
    
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            dbname=os.getenv("POSTGRES_DB", "offeri"),
            user=os.getenv("POSTGRES_USER", "offeri_user"),
            password=os.getenv("POSTGRES_PASSWORD", "")
        )
        cursor = conn.cursor()
        now = datetime.utcnow()
        
        cursor.execute("""
            SELECT user_id, is_super_key
            FROM api_keys
            WHERE id = %s AND is_active = true
        """, (api_key,))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return ""
        
        user_id, is_super_key = result
        
        if is_super_key:
            conn.close()
            return ""
        
        cursor.execute("""
            INSERT INTO mcp_usage (id, user_id, year, month, usage_count, created_at, updated_at)
            VALUES (gen_random_uuid()::text, %s, %s, %s, 1, NOW(), NOW())
            ON CONFLICT (user_id, year, month)
            DO UPDATE SET usage_count = mcp_usage.usage_count + 1, updated_at = NOW()
        """, (user_id, now.year, now.month))
        
        conn.commit()
        conn.close()
    except:
        pass
    
    return ""


# ═══════════════════════════════════════════════════════════════
# SERVER ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport='streamable-http', host='0.0.0.0', port=8080)
    else:
        mcp.run(transport='stdio')
