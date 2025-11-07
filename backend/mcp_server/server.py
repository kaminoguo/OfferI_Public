#!/usr/bin/env python3
"""
OfferI MCP Server - Workflow Orchestration Version 1.09

Architecture: Token-based workflow with classification-based filtering
- Each workflow tool returns a token required by the next tool
- Simplified single-pass processing (removed batch logic)
- Classification-based early filtering to reduce web search costs
- LLM knowledge-first approach with conditional web searches

Major Changes (v1.09):
- Tool 3: Classification-based filtering (NO MORE BATCH PROCESSING)
  * LLM gets all classifications from selected universities
  * LLM chooses relevant classifications based on student background
  * Only retrieves programs from selected classifications
  * All universities processed in single call (removed 5-university batch limit)
  * Dramatically reduces program count before name screening
- Tool 5: Simplified to single-round validation
  * Merged Round 3 (career-clarity filtering) + Round 4 (web search) into ONE round
  * LLM uses its own knowledge first
  * Only searches web if uncertain about specific program
  * Conditional web search reduces API costs
- Tool 7: Redesigned with focused Exa searches
  * DELETED: Exa searches for tuition, timeline, costs, deadlines
  * NEW: 2 targeted Exa searches per program:
    - Search 1: Curriculum/program structure/features (6-8 results)
    - Search 2: Career outcomes/student experience (6-8 results)
  * LLM can skip searches if it has sufficient knowledge
  * Focus: Program features + Student experience + Suitability analysis

Previous Changes (v1.08):
- Tool 5: Complete redesign of validation logic (validate_programs_with_exa → validate_programs_with_web)
  * Removed: Two-stage web search (Stage 1: admission cases, Stage 2: program quality)
  * New: Four-round filtering workflow
    - Round 3: Career-clarity-based strict filtering (before web search)
      * High clarity → Remove programs not matching career direction (宁缺毋滥)
      * Low clarity → Remove lower-tier universities (prioritize reputation)
      * Medium clarity → Balanced filtering
    - Round 4: Final filtering based on target audience match
  * Quality improvement: Career-aligned filtering BEFORE web search reduces noise

Previous Changes (v1.06):
- Tool 1-6: Career clarity-based ranking system
  * Tool 1: Added required career_clarity field (high/medium/low) in tier_assessment
  * Tool 2-5: Propagate career_clarity through token chain
  * Tool 6: Weighted scoring based on career clarity
    - High clarity (clear goals): 70% program fit, 30% university reputation
    - Medium clarity (general direction): 50% fit, 50% reputation
    - Low clarity (exploring): 30% fit, 70% reputation
  * University reputation scoring helper function added

Previous Changes (v1.05):
- Tool 7: Optimized search parameters based on empirical testing
  * Search 1: Precise university domain filtering (100% relevance vs 50%)
  * Search 3: Specific deadline keywords (100% relevance vs 0-25%)
  * Maintains backward compatibility while improving quality

Previous Changes (v1.04):
- Tool 1 & 5: Generic web search instead of Exa-specific
  * LLM can now choose ANY search tool (Exa, gemini-cli, Bright Data, etc.)
  * Parameters: exa_admission_searches → web_searches, exa_validations → web_validations
- Tool 7: Quality validation added
  * If universities > 7 but programs < 20, reject report

Previous Changes (v1.03):
- Tool 1: LLM-first with REQUIRED tier_assessment dict before optional searches
  * Forces LLM to analyze using knowledge base FIRST
  * Then decides if 0-3 web searches needed (max 25 results each)
- Tool 3-5: Strict batch processing workflow
  * Process ONE batch (5 universities) at a time

Optimization Summary:
- Tool 1: 95 results → 0-75 results (0-100% savings)
- Tool 5: Per-program search with skip optimization
  * 3-8 results per program (focused micro-searches)
  * LLM can skip well-known programs → variable cost based on knowledge
  * Career-based filtering BEFORE search reduces noise
- Tool 7: Domain-specific search optimization (50% → 100% relevance)

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
__version__ = "1.09"

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
    This server uses token-based workflow orchestration with batch processing:

    1. start_consultation() - LLM analyzes background FIRST, then optional 0-3 web searches (max 25 results each)
    2. explore_universities() - Get all universities in target country

    3-5. BATCH LOOP (process one batch at a time):
       3. get_university_programs() - Get programs for 5 universities (one batch)
       4. shortlist_programs_by_name() - Two-pass screening for THIS batch
       5. validate_programs_with_exa() - Two-stage web search validation for THIS batch
       → Repeat 3-5 for next batch until all universities processed

    6. score_and_rank_programs() - Score and rank all validated programs (after ALL batches complete)
    7. generate_final_report() - Generate comprehensive report with detailed research

    BATCH PROCESSING:
    - Tools 3-5 form a cycle: process ONE batch → move to next batch
    - Tool 5 uses previous_validation_token to chain batches
    - Tool 6 only callable when is_complete=True (all batches validated)

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

def _get_classifications_for_universities(university_names: List[str]) -> Dict[str, int]:
    """Internal: Get all unique classifications from multiple universities with program counts"""
    conn = get_db_connection()
    cursor = conn.cursor()

    placeholders = ','.join('?' * len(university_names))
    patterns = [f"%{uni}%" for uni in university_names]

    cursor.execute(f"""
        SELECT classification, COUNT(*) as count
        FROM programs
        WHERE ({' OR '.join(['LOWER(university_name) LIKE LOWER(?)' for _ in university_names])})
        AND classification IS NOT NULL
        GROUP BY classification
        ORDER BY count DESC
    """, patterns)
    results = cursor.fetchall()
    conn.close()

    return {row["classification"]: row["count"] for row in results}

def _search_programs(university_name: str, classification_filters: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Internal: Get programs for a university, optionally filtered by classifications"""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT program_id, program_name, classification
        FROM programs
        WHERE LOWER(university_name) LIKE LOWER(?)
    """
    params = [f"%{university_name}%"]

    if classification_filters:
        placeholders = ','.join('?' * len(classification_filters))
        query += f" AND classification IN ({placeholders})"
        params.extend(classification_filters)

    query += " ORDER BY program_name"

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    return [{"id": row["program_id"], "name": row["program_name"], "classification": row["classification"]} for row in results]

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
               duration_months, study_mode, classification
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
            "duration_months": row["duration_months"],
            "classification": row["classification"]
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


def _estimate_university_reputation(uni_name_lower: str) -> float:
    """
    Estimate university reputation score (0-100 scale) based on university name.
    This is a simplified heuristic for scoring. In production, use actual ranking data.

    Args:
        uni_name_lower: University name in lowercase

    Returns:
        Reputation score (0-100)
    """
    # Top-tier universities (95-100)
    top_tier_keywords = [
        "stanford", "mit", "harvard", "berkeley", "cmu", "carnegie mellon",
        "oxford", "cambridge", "imperial", "eth zurich",
        "national university of singapore", "nus", "nanyang", "ntu",
        "tsinghua", "peking", "hku", "university of hong kong",
        "hkust", "hong kong university of science", "cuhk", "chinese university of hong kong"
    ]

    # High-tier universities (85-94)
    high_tier_keywords = [
        "cornell", "columbia", "princeton", "yale", "upenn", "pennsylvania",
        "michigan", "ucla", "ucsd", "usc", "georgia tech",
        "toronto", "waterloo", "mcgill", "ubc",
        "cityu", "city university of hong kong", "polyu", "polytechnic university"
    ]

    # Mid-tier universities (70-84)
    mid_tier_keywords = [
        "washington", "wisconsin", "illinois", "texas", "boston university",
        "northeastern", "purdue", "duke", "northwestern"
    ]

    # Check tier membership
    for keyword in top_tier_keywords:
        if keyword in uni_name_lower:
            return 97.0

    for keyword in high_tier_keywords:
        if keyword in uni_name_lower:
            return 89.0

    for keyword in mid_tier_keywords:
        if keyword in uni_name_lower:
            return 77.0

    # Default for other validated universities
    return 70.0


# ═══════════════════════════════════════════════════════════════
# WORKFLOW ORCHESTRATION TOOLS
# ═══════════════════════════════════════════════════════════════

@mcp.tool
async def start_consultation(
    background: str,
    tier_assessment: dict,
    web_searches: Optional[List[dict]] = None
) -> dict:
    """
    Step 1: Start consultation session

    PURPOSE: Determine what tier of schools the student can target (e.g., Top 10, Top 30, Top 50)

    ⚠️ CRITICAL WORKFLOW - YOU MUST FOLLOW THIS ORDER:

    STEP 1: ANALYZE FIRST (using your knowledge base)
    - Analyze GPA, school tier, major, internships, projects, awards
    - Make initial tier judgment based on your knowledge (up to January 2025)
    - Prepare tier_assessment dict with your analysis

    STEP 2: DECIDE IF YOU NEED TO SEARCH (0-3 times max)
    - ✅ Search if: Borderline GPA for target tier, unique compensating factors, 2024-2025 trend uncertainties
    - ❌ DO NOT search if: Obviously strong profile or obviously weak profile
    - If searching: Find similar admission cases to validate tier judgment
    - Use your built-in web search capability

    STEP 3: CALL THIS TOOL
    - Submit background + tier_assessment + optional web_searches

    Search query construction (only if uncertain):
    - Include: student's school tier, GPA range, major field, key experience type
    - Include: target country, target tier
    - Example pattern: "[School Tier] [Major] [GPA Range] [Key Experience] admitted [Target Country] [Tier] programs"

    Args:
        background: Student background (free text - GPA, university, internships, projects, etc.)
        tier_assessment: REQUIRED dict with your tier judgment:
            {
                "target_tier_range": "Top 20-50",  # Overall target range
                "reach_tier": "Top 10-20",         # Ambitious schools
                "match_tier": "Top 20-40",         # Realistic schools
                "safety_tier": "Top 40-60",        # Safe schools
                "key_strengths": ["Industry internship", "Strong projects", "Research publications", ...],
                "key_weaknesses": ["Below average GPA", "Limited research experience", ...]
                "career_clarity": "high",  # high/medium/low - affects ranking weights
                    # high: Clear career goals/interests (e.g., "Machine learning research", "Corporate strategy")
                    #       → Prioritize program fit over university reputation
                    # medium: General direction (e.g., "Technology sector", "Finance industry")
                    #       → Balanced weights
                    # low: Uncertain/exploring (e.g., "Still deciding", "Keeping options open")
                    #       → Prioritize university reputation over program fit
                "reasoning": "Example: Strong technical background but borderline GPA, compensated by internships..."
            }
        web_searches: Optional list of 0-3 web search results (using your built-in search)
            Each: {"query": "...", "num_results": <1-25>, "key_findings": "..."}
            ONLY include if genuinely uncertain after knowledge-based analysis

    Returns:
        consultation_token + validated tier assessment + next_step instructions
    """
    # ═══════════════════════════════════════════════════════════════
    # QUOTA VALIDATION (v1.16)
    # ═══════════════════════════════════════════════════════════════
    import psycopg2
    from fastmcp.server.dependencies import get_http_headers

    FREE_CONSULTATION_LIMIT = 5  # 5 free consultations per month

    # Get API key from headers
    api_key = ""
    try:
        headers = get_http_headers()
        auth_header = headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
    except:
        api_key = os.getenv("SSE_API_KEY", "")

    if not api_key or not api_key.startswith("sk_"):
        raise ValueError("❌ Invalid or missing API key. Please provide a valid API key in Authorization header.")

    # Check quota in database
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

        # Get user_id and check if super key
        cursor.execute("""
            SELECT user_id, is_super_key, is_active
            FROM api_keys
            WHERE id = %s
        """, (api_key,))
        result = cursor.fetchone()

        if not result:
            conn.close()
            raise ValueError(f"❌ API key not found or invalid: {api_key[:20]}...")

        user_id, is_super_key, is_active = result

        if not is_active:
            conn.close()
            raise ValueError(f"❌ API key has been revoked. Please generate a new key at https://offeri.org/dashboard")

        # Super keys have unlimited access
        if is_super_key:
            conn.close()
            # No quota check needed for super keys
        else:
            # Check current month usage
            usage_id = f"{user_id}_{now.year}_{now.month}"
            cursor.execute("""
                SELECT usage_count FROM mcp_usage
                WHERE id = %s
            """, (usage_id,))
            usage_result = cursor.fetchone()

            current_usage = usage_result[0] if usage_result else 0

            if current_usage >= FREE_CONSULTATION_LIMIT:
                conn.close()
                raise ValueError(
                    f"❌ MONTHLY QUOTA EXCEEDED\n\n"
                    f"You've used all {FREE_CONSULTATION_LIMIT} free consultations this month ({now.year}-{now.month:02d}).\n\n"
                    f"📊 Usage: {current_usage}/{FREE_CONSULTATION_LIMIT}\n"
                    f"📅 Resets: {now.year}-{(now.month % 12) + 1:02d}-01\n\n"
                    f"💡 Options:\n"
                    f"  1. Wait for monthly reset (1st of next month)\n"
                    f"  2. Contact us for unlimited Super API keys: support@offeri.org\n"
                )

            conn.close()

    except ValueError:
        # Re-raise validation errors (quota exceeded, invalid key, etc.)
        raise
    except Exception as e:
        # Log database errors but don't block (fail-open for reliability)
        print(f"⚠️ Quota check failed (database error): {e}")
        pass

    # ═══════════════════════════════════════════════════════════════
    # END QUOTA VALIDATION
    # ═══════════════════════════════════════════════════════════════

    # Validate tier_assessment
    if not tier_assessment or not isinstance(tier_assessment, dict):
        raise ValueError("tier_assessment is required and must be a dict")

    required_fields = ["target_tier_range", "reach_tier", "match_tier", "safety_tier", "career_clarity", "reasoning"]
    missing_fields = [field for field in required_fields if field not in tier_assessment]
    if missing_fields:
        raise ValueError(f"tier_assessment missing required fields: {missing_fields}")

    # Validate career_clarity value
    career_clarity = tier_assessment.get("career_clarity", "").lower()
    if career_clarity not in ["high", "medium", "low"]:
        raise ValueError(f"career_clarity must be 'high', 'medium', or 'low'. You provided: '{tier_assessment.get('career_clarity')}'")

    # Validate optional searches
    search_count = 0
    if web_searches:
        if not isinstance(web_searches, list):
            raise ValueError("web_searches must be a list")

        if len(web_searches) > 3:
            raise ValueError(f"Maximum 3 web searches allowed. You provided {len(web_searches)}.")

        for i, search in enumerate(web_searches):
            if not isinstance(search, dict) or "query" not in search or "num_results" not in search:
                raise ValueError(f"Search #{i+1} must be a dict with 'query' and 'num_results' fields")

            num_results = search["num_results"]
            if not isinstance(num_results, int) or num_results < 1 or num_results > 25:
                raise ValueError(f"Search #{i+1}: num_results must be 1-25. You provided {num_results}")

        search_count = len(web_searches)

    token = generate_token("consultation", {
        "background": background,
        "tier_assessment": tier_assessment,
        "web_searches_completed": search_count,
        "web_searches_data": web_searches or []
    })

    return {
        "consultation_token": token,
        "tier_assessment": tier_assessment,
        "web_searches_completed": search_count,
        "instructions": f"""
✅ Tier assessment complete. {'Used knowledge base only.' if search_count == 0 else f'Validated with {search_count} admission case search(es).'}

📊 TIER ASSESSMENT RESULTS:
- Target Range: {tier_assessment.get('target_tier_range', 'N/A')}
- Reach: {tier_assessment.get('reach_tier', 'N/A')}
- Match: {tier_assessment.get('match_tier', 'N/A')}
- Safety: {tier_assessment.get('safety_tier', 'N/A')}

{'🎯 Knowledge-First: Profile clearly maps to known tier ranges.' if search_count == 0 else f'🔍 Case Validation: Confirmed tier judgment with {search_count} similar case(s).'}

Next: Call explore_universities(country, consultation_token)
        """,
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
    consultation_data = validate_token(consultation_token, "consultation")

    # Extract career_clarity for later use in scoring
    tier_assessment = consultation_data.get("tier_assessment", {})
    career_clarity = tier_assessment.get("career_clarity", "medium")

    universities = _list_universities(country)

    if not universities:
        available = _get_available_countries()
        countries_str = ", ".join([f"{c['country']} ({c['count']})" for c in available[:10]])
        raise ValueError(f"Country '{country}' not found. Available: {countries_str}")

    token = generate_token("exploration", {
        "country": country,
        "universities": universities,
        "total_universities": len(universities),
        "career_clarity": career_clarity  # Pass through for scoring
    })
    
    return {
        "exploration_token": token,
        "universities": universities,
        "total_count": len(universities),
        "instructions": """
Review university list. Select ALL appropriate ones based on:
- School tier matches student credentials?
- Values student's strengths (internships/projects/awards)?
- Supports student's career goals?

💡 Selection Strategy:
- Be comprehensive (not just "famous Top 20")
- Consider fit over fame
- Include reach/match/safety schools across the tier spectrum

Next: Call get_university_programs(universities, exploration_token) with your selected universities
        """,
        "next_step": "Call get_university_programs(universities, exploration_token)"
    }


@mcp.tool
async def get_university_programs(
    universities: List[str],
    selected_classifications: List[str],
    exploration_token: str
) -> dict:
    """
    Step 3: Get programs filtered by classifications (NO BATCH PROCESSING)

    🏷️ WORKFLOW:
    1. LLM receives list of universities from explore_universities()
    2. LLM calls THIS tool to get all available classifications for those universities
    3. LLM reviews classifications and chooses relevant ones based on student background
    4. LLM calls this tool AGAIN with selected_classifications to retrieve filtered programs
    5. Proceed to TWO-PASS name screening (shortlist_programs_by_name)

    Args:
        universities: List of ALL selected university names (no limit)
        selected_classifications: List of classification names to filter by
            - Pass empty list [] on FIRST call to get available classifications
            - Pass selected classifications on SECOND call to get filtered programs
        exploration_token: From explore_universities()

    Returns:
        - First call (selected_classifications=[]): Available classifications with counts
        - Second call (with classifications): programs_token + filtered programs

    Example workflow:
        # Call 1: Get classifications
        result1 = get_university_programs(
            universities=["CMU", "Stanford", "MIT"],
            selected_classifications=[],  # Empty = get classifications
            exploration_token="..."
        )
        # Returns: {"Computer Science & IT": 450, "Management": 200, ...}

        # Call 2: Get programs with selected classifications
        result2 = get_university_programs(
            universities=["CMU", "Stanford", "MIT"],
            selected_classifications=["Computer Science & IT", "Electrical Engineering"],
            exploration_token="..."
        )
        # Returns: programs_token + filtered programs
    """
    exploration_data = validate_token(exploration_token, "exploration")
    career_clarity = exploration_data.get("career_clarity", "medium")

    if not universities or not isinstance(universities, list):
        raise ValueError("You must provide a list of university names")

    if not isinstance(selected_classifications, list):
        raise ValueError("selected_classifications must be a list (use [] to get available classifications)")

    # FIRST CALL: Return available classifications
    if len(selected_classifications) == 0:
        classifications = _get_classifications_for_universities(universities)

        return {
            "available_classifications": classifications,
            "total_classifications": len(classifications),
            "total_programs": sum(classifications.values()),
            "instructions": f"""
📊 CLASSIFICATION ANALYSIS COMPLETE

Found {len(classifications)} unique classifications across {len(universities)} universities:

{chr(10).join([f"  • {name}: {count} programs" for name, count in list(classifications.items())[:15]])}
{"  ... and more" if len(classifications) > 15 else ""}

🎯 YOUR TASK: Select relevant classifications based on student background

SELECTION STRATEGY:
1. PRIMARY classifications: Direct match with student's major/field
   Example: CS student → ["Computer Science & IT", "Electrical & Electronics Engineering"]
   Example: Business student → ["Management & Administration", "Finance, Banking & Insurance"]
   Example: Liberal Arts → ["Literature & Linguistics", "Philosophy, Theology & Media"]

2. SECONDARY classifications: Related/complementary fields
   Example: CS student might also consider ["Mathematics", "Statistics"]
   Example: Research-oriented might include research-heavy interdisciplinary fields

3. AVOID: Obviously irrelevant fields
   Example: CS student should NOT select ["Music & Performing Arts", "Veterinary"]

⚠️ IMPORTANT: Be inclusive but sensible
- Research students: Include research-focused classifications
- Career students: Include professional/applied classifications
- Liberal Arts: Don't limit to humanities - interdisciplinary programs matter

📋 NEXT STEP:
Call get_university_programs() AGAIN with your selected classifications:

get_university_programs(
    universities={universities},
    selected_classifications=["Classification 1", "Classification 2", ...],
    exploration_token="{exploration_token}"
)
            """,
            "next_step": "Review classifications and call this tool again with selected_classifications"
        }

    # SECOND CALL: Return filtered programs
    all_programs = {}
    total_programs = 0
    classification_stats = {}

    for uni in universities:
        programs = _search_programs(uni, classification_filters=selected_classifications)
        if programs:
            all_programs[uni] = programs
            total_programs += len(programs)

            # Track classification distribution
            for prog in programs:
                class_name = prog.get("classification", "Unknown")
                classification_stats[class_name] = classification_stats.get(class_name, 0) + 1

    token = generate_token("programs", {
        "universities": universities,
        "all_programs": all_programs,
        "total_programs": total_programs,
        "career_clarity": career_clarity,
        "selected_classifications": selected_classifications,
        "classification_statistics": classification_stats
    })

    return {
        "programs_token": token,
        "programs_by_university": all_programs,
        "total_programs": total_programs,
        "universities_count": len(all_programs),
        "selected_classifications": selected_classifications,
        "classification_statistics": classification_stats,
        "instructions": f"""
✅ CLASSIFICATION FILTERING COMPLETE

📊 RESULTS:
- Universities: {len(universities)}
- Selected classifications: {len(selected_classifications)}
- Total programs retrieved: {total_programs}

🏷️  CLASSIFICATION DISTRIBUTION:
{chr(10).join([f"  • {name}: {count} programs" for name, count in sorted(classification_stats.items(), key=lambda x: x[1], reverse=True)])}

📋 NEXT STEP: TWO-PASS NAME SCREENING

PASS 1 - Remove Obvious Mismatches (排除法):
- Review program NAMES carefully
- Remove programs with misleading names even if classification seems right
- Example: Remove "Art Technology" if student wants pure CS (even if classified as CS)
- Philosophy: 宁少不多 (fewer but better matches)

PASS 2 - Select Relevant Programs (选择法):
- From remaining programs, positively SELECT those matching student profile
- Consider: Specific interests, career goals, research vs coursework preference
- Include borderline cases (will be validated in next step)

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
    Step 4: Shortlist programs by name analysis (PASS 2 ONLY)

    This is PASS 2 of TWO-PASS screening (classifications already filtered in Step 3):
    - PASS 1 (Tool 3): Classification filtering
    - PASS 2 (THIS TOOL): Name-based selection

    YOUR TASK: Review program NAMES and select those matching student profile
    - Remove misleading program names even if classification seems right
    - Select programs that align with specific interests, career goals
    - Include borderline cases (will be validated in Step 5)

    Args:
        shortlisted_by_university: Dict mapping university name to list of program IDs
            Example: {
                "CMU": [123, 456, 789],
                "Stanford": [234, 567],
                ...
            }
        programs_token: From get_university_programs()

    Returns:
        shortlist_token + statistics + instructions for Step 5
    """
    programs_data = validate_token(programs_token, "programs")
    career_clarity = programs_data.get("career_clarity", "medium")

    if not shortlisted_by_university or not isinstance(shortlisted_by_university, dict):
        raise ValueError("You must provide shortlisted_by_university as a dict")

    total_shortlisted = sum(len(ids) for ids in shortlisted_by_university.values())

    if total_shortlisted == 0:
        raise ValueError("You must shortlist at least some programs. Did you review the program names?")

    token = generate_token("shortlist", {
        "universities": list(shortlisted_by_university.keys()),
        "shortlisted_by_university": shortlisted_by_university,
        "total_shortlisted": total_shortlisted,
        "career_clarity": career_clarity
    })

    return {
        "shortlist_token": token,
        "shortlisted_by_university": shortlisted_by_university,
        "total_shortlisted": total_shortlisted,
        "universities_count": len(shortlisted_by_university),
        "instructions": f"""
✅ NAME SCREENING COMPLETE: {total_shortlisted} programs from {len(shortlisted_by_university)} universities

📋 NEXT STEP: Single-round validation with conditional web search

YOUR TASK: For each program, use YOUR OWN KNOWLEDGE first:
1. Evaluate program features (curriculum, focus, teaching style)
2. Identify target student profile (what background does this program seek?)
3. Match against student's background and goals

ONLY SEARCH IF UNCERTAIN:
- If you don't know the program well → Search web for program details
- Query: "[University] [Program Name] target audience curriculum student experience"
- If you DO know the program → Skip search, use your knowledge

FINAL DECISION: Keep or remove based on:
- Program-student fit
- Target audience match
- Career/research goal alignment

Call validate_programs_with_web(web_validations, shortlist_token)
        """,
        "next_step": "Call validate_programs_with_web(web_validations, shortlist_token)"
    }


@mcp.tool
async def validate_programs_with_web(
    validated_programs: Dict[str, List[int]],
    shortlist_token: str,
    optional_web_searches: Optional[Dict[str, dict]] = None
) -> dict:
    """
    Step 5: Single-round validation with conditional web search

    🎯 SIMPLIFIED WORKFLOW (v1.09):
    Merged Round 3 (career-clarity filtering) + Round 4 (web search) into ONE round.

    YOUR TASK:
    1. Review shortlisted programs using your own knowledge FIRST
    2. Consider career clarity from consultation:
       - career_clarity = "high": Strictly match career direction, remove misaligned programs
       - career_clarity = "low": Prioritize university reputation over program fit
       - career_clarity = "medium": Balance both fit and reputation
    3. For programs where you're UNCERTAIN about fit/target audience, optionally search web
    4. Return final validated program IDs per university

    Args:
        validated_programs: Dict mapping university name to final program IDs
            Example: {
                "CMU": [123, 456],
                "Stanford": [789, 234],
                ...
            }

        shortlist_token: From shortlist_programs_by_name()

        optional_web_searches: OPTIONAL dict with web searches for programs you're uncertain about
            Example: {
                "CMU MISM (123)": {
                    "query": "CMU MISM target audience ideal candidates background",
                    "num_results": 5,
                    "findings": "Based on web search: Program targets...",
                    "reasoning": "Searched because unclear if business background required"
                },
                "Stanford MSCS (789)": {
                    "skipped": true,
                    "known_info": "Standard CS MS program, targets strong CS undergrads",
                    "reasoning": "Well-known program, no search needed"
                }
            }

            ⚠️ ONLY include programs where you need external validation
            - Skip search if you know the program well
            - Query pattern: "[University] [Program Name] target audience ideal candidates"
            - num_results: 3-8 (defaults to 5)

    Returns:
        validation_token + statistics + next_step instructions
    """
    shortlist_data = validate_token(shortlist_token, "shortlist")
    career_clarity = shortlist_data.get("career_clarity", "medium")
    expected_unis = shortlist_data["universities"]

    if not validated_programs or not isinstance(validated_programs, dict):
        raise ValueError("You must provide validated_programs as a dict")

    # Validate university names
    current_unis = set(validated_programs.keys())
    invalid_unis = [uni for uni in current_unis if uni not in expected_unis]
    if invalid_unis:
        raise ValueError(
            f"Invalid university names: {invalid_unis}\n\n"
            f"These universities were not in your shortlist.\n"
            f"Valid university names: {expected_unis}\n\n"
            f"Tip: Copy exact names from shortlist_programs_by_name response."
        )

    # Collect all final program IDs and validate
    all_final_ids = []
    errors = []

    for uni, program_ids in validated_programs.items():
        if not isinstance(program_ids, list):
            errors.append(f"• {uni}: program_ids must be a list")
            continue

        if len(program_ids) == 0:
            errors.append(f"• {uni}: empty program list (must select at least one program)")
            continue

        all_final_ids.extend(program_ids)

    if errors:
        error_msg = f"Found {len(errors)} validation error(s):\n\n" + "\n".join(errors)
        error_msg += "\n\n💡 Tip: Fix all errors listed above and retry."
        raise ValueError(error_msg)

    if len(all_final_ids) == 0:
        raise ValueError("No programs validated. You must select at least one program per university.")

    # Count web searches if provided
    total_searches = 0
    total_skipped = 0
    if optional_web_searches:
        for search_data in optional_web_searches.values():
            if search_data.get("skipped", False):
                total_skipped += 1
            else:
                total_searches += 1

    token = generate_token("validation", {
        "validated_universities": list(current_unis),
        "final_program_ids": all_final_ids,
        "validated_programs": validated_programs,
        "web_searches": optional_web_searches or {},
        "career_clarity": career_clarity
    })

    return {
        "validation_token": token,
        "universities_validated": len(validated_programs),
        "total_programs_validated": len(all_final_ids),
        "web_searches_performed": total_searches,
        "programs_validated_with_knowledge": total_skipped,
        "message": f"✅ Validated {len(all_final_ids)} programs from {len(validated_programs)} universities\n({total_searches} web searches, {total_skipped} validated with own knowledge)",
        "next_step": "Call score_and_rank_programs(validation_token)"
    }


@mcp.tool
async def score_and_rank_programs(
    validation_token: str
) -> dict:
    """
    Step 6: Score and rank all validated programs

    Args:
        validation_token: From validate_programs_with_web()

    Returns:
        ranking_token + top programs + required Exa search count for detailed research
    """
    validation_data = validate_token(validation_token, "validation")
    career_clarity = validation_data.get("career_clarity", "medium")

    final_ids = validation_data["final_program_ids"]
    universities_count = len(validation_data.get("validated_universities", []))

    # Get program details
    programs = _get_program_details_batch(final_ids)

    # Calculate weighted scores based on career clarity
    # Career clarity affects weight distribution between reputation and program fit

    # Define scoring weights based on career clarity
    if career_clarity == "high":
        reputation_weight = 0.3
        fit_weight = 0.7
    elif career_clarity == "low":
        reputation_weight = 0.7
        fit_weight = 0.3
    else:  # medium
        reputation_weight = 0.5
        fit_weight = 0.5

    # Score each program
    for program in programs:
        # Simple reputation score based on university tier (0-100 scale)
        # This is a simplified proxy - in production would use actual rankings
        uni_name = program["university_name"].lower()
        reputation_score = _estimate_university_reputation(uni_name)

        # Simple fit score based on program characteristics (0-100 scale)
        # Programs that passed Exa validation are already relevant, so base score is high
        fit_score = 85  # Base score for validated programs

        # Calculate weighted final score
        program["reputation_score"] = reputation_score
        program["fit_score"] = fit_score
        program["score"] = reputation_score * reputation_weight + fit_score * fit_weight

    # Sort by score descending
    programs.sort(key=lambda x: x["score"], reverse=True)

    # Assign ranks
    for i, program in enumerate(programs):
        program["rank"] = i + 1
    
    # Determine report format
    if universities_count >= 7:
        report_format = "TOP_20"
        detailed_count = 10  # Tier 1: Full Exa research
        concise_count = 10   # Tier 2: Concise summaries (LLM knowledge allowed)
        required_searches = 20  # Tier 1 only: 10 programs × 2 searches = 20 (v1.09)
    else:
        report_format = "TOP_10"
        detailed_count = 5   # Tier 1: Full Exa research
        concise_count = 0    # No Tier 2 for small selection
        required_searches = 10  # 5 programs × 2 searches = 10 (v1.09)

    top_programs = programs[:detailed_count + concise_count]

    token = generate_token("ranking", {
        "report_format": report_format,
        "detailed_tier_count": detailed_count,
        "concise_tier_count": concise_count,  # v1.15: Added for Tier 2
        "required_exa_searches": required_searches,
        "top_programs": top_programs,
        "total_universities_validated": universities_count,
        "career_clarity": career_clarity,
        "reputation_weight": reputation_weight,
        "fit_weight": fit_weight
    })
    
    return {
        "ranking_token": token,
        "report_format": report_format,
        "detailed_tier_programs": detailed_count,
        "concise_tier_programs": concise_count,  # v1.15: Fixed to use concise_count
        "total_top_programs": len(top_programs),
        "required_exa_searches": required_searches,
        "top_programs": top_programs,
        "instructions": f"""
✅ Scored and ranked all programs.

Report format: {report_format}
- Tier 1 (detailed): {detailed_count} programs
- Tier 2 (concise): {concise_count} programs

📋 TWO-TIER RESEARCH WORKFLOW (v1.09):

TIER 1 (Detailed Research) - {detailed_count} programs:
- Perform 2 Exa searches per program (curriculum + career outcomes)
- Focus on program features, student experience, and suitability analysis
- NO searches for tuition/timeline/costs (those change frequently)
- Total: {required_searches} Exa searches required

TIER 2 (Concise Summary) - {concise_count} programs:
- NO Exa searches required (use your knowledge base up to Jan 2025)
- Provide concise summary with 3 fields:
  * quick_facts: Basic info (duration, format, study mode)
  * fit_reasoning: Why recommend for this student
  * application_notes: Key application requirements
- Source: mark as "llm_knowledge"

🎯 Tier 1 Search Strategy:
1. FIRST: Check if you already know the program well
2. IF uncertain: Use Exa MCP (mcp__exa__web_search_exa)
3. IF Exa returns no useful results: Use your own knowledge
4. ALWAYS fill "findings" field with detailed content (min 50 chars)

For EACH of the top {detailed_count} programs (Tier 1), do EXACTLY 2 Exa searches:

🔍 Search 1: Curriculum & Program Structure (6-8 results)
Query: "[University] [Program] curriculum courses structure faculty specializations"

Recommended Exa MCP Parameters:
mcp__exa__web_search_exa(
    query="<constructed query>",
    numResults=7,
    useAutoprompt=true,
    searchType="auto",
    includeDomains=["<university_domain>"],  # Use university domain for authoritative info
    useHighlights=true,               # CRITICAL: Reduce tokens
    highlightNumSentences=8,
    highlightPerUrl=6
)

Then fill findings field:
- If Exa found info: "findings": "Based on Exa search: Core courses include X, Y, Z. Specializations in..."
- If Exa failed OR you know the program: "findings": "Based on general knowledge: Program covers..."

🔍 Search 2: Career Outcomes & Student Experience (6-8 results)
Query: "[University] [Program] career outcomes employment alumni student experience reviews"

Recommended Exa MCP Parameters:
mcp__exa__web_search_exa(
    query="<constructed query>",
    numResults=7,
    useAutoprompt=true,
    searchType="auto",
    # NO includeDomains - need diverse sources (official stats + student reviews + career reports)
    useHighlights=true,               # CRITICAL: Reduce tokens
    highlightNumSentences=8,
    highlightPerUrl=6
)

Then fill findings field:
- If Exa found info: "findings": "Based on Exa search: 95% employment rate, avg salary $X, top employers..."
- If Exa failed OR you know the program: "findings": "Based on general knowledge: Strong career outcomes..."

⚠️ CONDITIONAL SEARCHING (v1.09 key feature):
- SKIP search if you have sufficient knowledge about the program
- Mark as source="llm_knowledge" when using your knowledge
- Mark as source="exa" when using Exa search results
- This reduces costs while maintaining quality

Total: {required_searches} Exa searches maximum ({detailed_count} programs × 2 searches)
Actual searches may be fewer if you know programs well!

Work systematically:
1. Complete all Tier 1 programs (0-2 searches each): Program #1 → #2 → ... → #{detailed_count}
2. Then provide Tier 2 concise summaries (knowledge-based): Program #{detailed_count+1} → ... → #{detailed_count + concise_count}
3. Call generate_final_report(detailed_research, ranking_token, concise_research)
        """,
        "next_step": f"Complete {required_searches} Exa searches for Tier 1, then provide Tier 2 summaries, then call generate_final_report()"
    }


@mcp.tool
async def generate_final_report(
    detailed_program_research: List[dict],
    ranking_token: str,
    concise_program_research: Optional[List[dict]] = None
) -> dict:
    """
    Step 7: Generate comprehensive two-tier report (v1.09)

    Focus: Program features, student experience, and suitability analysis
    NO searches for tuition/timeline/costs (those change frequently and are not program-specific)

    Args:
        detailed_program_research: Tier 1 programs with 2 Exa searches each
            Each: {
                "program_id": 123,
                "exa_searches": [
                    {
                        "query": "CMU MISM curriculum courses structure faculty",
                        "num_results": 7,
                        "findings": "Based on Exa search: Core courses include analytics, business intelligence...",
                        "source": "exa"  # Optional: "exa" or "llm_knowledge"
                    },
                    {
                        "query": "CMU MISM career outcomes employment alumni experience",
                        "num_results": 7,
                        "findings": "Based on Exa search: 95% employment rate, avg salary $120k, top employers...",
                        "source": "exa"
                    }
                ],
                "analysis": {
                    "program_features": "Description of unique program characteristics, curriculum structure, faculty expertise...",
                    "student_experience": "What it's like to study in this program, learning format, intensity, culture...",
                    "suitability_analysis": "Why this program matches the student's background, goals, and profile..."
                }
            }

        ⚠️ CRITICAL: "findings" field is REQUIRED and MUST be non-empty (min 50 chars)
        - FIRST: Check if you know the program well
        - IF uncertain: Use Exa MCP search (mcp__exa__web_search_exa)
        - IF Exa returns no useful results: Use your own knowledge and mark source="llm_knowledge"
        - NEVER submit empty findings or skip this field

        ⚠️ CONDITIONAL SEARCHING (v1.09):
        - You can skip searches for well-known programs
        - Mark source="llm_knowledge" when using your knowledge
        - This reduces costs while maintaining quality

        concise_program_research: Tier 2 programs with concise summaries (TOP_20 format only)
            Each: {
                "program_id": 456,
                "summary": {
                    "quick_facts": "1-year MS, STEM-designated, full-time/part-time options",
                    "fit_reasoning": "Strong PM training with tech emphasis, matches Google PM experience. Industry partnerships.",
                    "application_notes": "Typical deadlines Jan-Mar, requires statement of purpose, GRE optional, 3.0+ GPA recommended"
                },
                "source": "llm_knowledge"
            }

        ⚠️ TIER 2 REQUIREMENTS:
        - Required when report_format="TOP_20" (≥7 universities selected)
        - NO Exa searches needed - use your knowledge base
        - Each field in summary must be ≥30 characters
        - quick_facts: Basic program facts (duration, format, study mode)
        - fit_reasoning: Why suitable for this student's profile
        - application_notes: Key application requirements (NO specific dates)

        ranking_token: From score_and_rank_programs()

    Returns:
        Validation confirmation + instructions to generate report
    """
    ranking_data = validate_token(ranking_token, "ranking")

    report_format = ranking_data["report_format"]
    detailed_count = ranking_data["detailed_tier_count"]
    concise_count = ranking_data.get("concise_tier_count", 0)  # v1.15: Get Tier 2 count
    required_searches = ranking_data["required_exa_searches"]

    # v1.15: Validate Tier 1 (detailed) count based on token contract
    if not detailed_program_research or len(detailed_program_research) != detailed_count:
        raise ValueError(
            f"Tier 1 (detailed): Expected {detailed_count} programs, got {len(detailed_program_research) if detailed_program_research else 0}.\n\n"
            f"You must provide research for EXACTLY {detailed_count} Tier 1 programs with full Exa searches."
        )

    # v1.15: Validate Tier 2 (concise) only if report_format requires it
    if concise_count > 0:
        if not concise_program_research:
            raise ValueError(
                f"Tier 2 (concise): {report_format} format requires Tier 2 summaries.\n\n"
                f"Provide concise_program_research with {concise_count} programs.\n\n"
                f"Tier 2 does NOT require Exa searches - use your knowledge base."
            )
        if len(concise_program_research) != concise_count:
            raise ValueError(
                f"Tier 2 (concise): Expected {concise_count} programs, got {len(concise_program_research)}."
            )

    total_searches = 0
    validation_results = []
    
    for i, research in enumerate(detailed_program_research):
        program_id = research.get("program_id")
        exa_searches = research.get("exa_searches", [])
        dimensions = research.get("dimensions", {})
        
        if not program_id:
            raise ValueError(f"Research #{i+1}: missing program_id")

        if len(exa_searches) != 2:
            raise ValueError(f"Program {program_id}: must have EXACTLY 2 Exa searches (v1.09). You provided {len(exa_searches)}.")

        # Validate each search with flexible result count (6-8 results)
        search_names = ["Curriculum & Structure", "Career Outcomes & Experience"]

        for j, search in enumerate(exa_searches):
            if not isinstance(search, dict):
                raise ValueError(f"Program {program_id}, Search #{j+1} ({search_names[j]}): must be a dict")

            # Validate num_results (flexible 6-8 range)
            if "num_results" not in search:
                raise ValueError(f"Program {program_id}, Search #{j+1} ({search_names[j]}): missing 'num_results' field")

            actual = search["num_results"]

            if not (6 <= actual <= 8):
                raise ValueError(
                    f"Program {program_id}, Search #{j+1} ({search_names[j]}): "
                    f"num_results must be 6-8. You provided {actual}"
                )

            # NEW: Validate findings field (CRITICAL for preventing Exa bypass)
            if "findings" not in search:
                raise ValueError(
                    f"Program {program_id}, Search #{j+1} ({search_names[j]}): missing 'findings' field.\n"
                    f"You MUST perform Exa search OR use LLM knowledge if Exa fails."
                )

            findings = search["findings"]
            if not findings or not isinstance(findings, str):
                raise ValueError(
                    f"Program {program_id}, Search #{j+1} ({search_names[j]}): 'findings' must be a non-empty string"
                )

            # Ensure findings has substantial content (at least 50 characters)
            if len(findings.strip()) < 50:
                raise ValueError(
                    f"Program {program_id}, Search #{j+1} ({search_names[j]}): "
                    f"'findings' too short ({len(findings.strip())} chars). Provide detailed findings (min 50 chars)."
                )

            # Optional: Validate source field if provided
            if "source" in search:
                valid_sources = ["exa", "llm_knowledge"]
                if search["source"] not in valid_sources:
                    raise ValueError(
                        f"Program {program_id}, Search #{j+1} ({search_names[j]}): "
                        f"'source' must be one of {valid_sources}. You provided: {search['source']}"
                    )

            total_searches += 1

        # v1.09: Validate new analysis structure (3 sections instead of 6 dimensions)
        analysis = research.get("analysis", {})
        if not isinstance(analysis, dict):
            raise ValueError(f"Program {program_id}: 'analysis' must be a dict")

        required_sections = ["program_features", "student_experience", "suitability_analysis"]
        missing_sections = [sec for sec in required_sections if sec not in analysis]
        if missing_sections:
            raise ValueError(f"Program {program_id}: missing analysis sections: {missing_sections}")

        # Validate each section has substantial content
        for section in required_sections:
            content = analysis[section]
            if not isinstance(content, str) or len(content.strip()) < 100:
                raise ValueError(
                    f"Program {program_id}: '{section}' must be a string with at least 100 characters. "
                    f"You provided {len(content.strip()) if isinstance(content, str) else 0} chars."
                )

        validation_results.append({
            "program_id": program_id,
            "tier": 1,
            "exa_searches_count": len(exa_searches),
            "analysis_complete": True
        })

    # v1.15: Validate Tier 2 (concise) programs - RELAXED validation
    if concise_program_research:
        for i, research in enumerate(concise_program_research):
            program_id = research.get("program_id")
            summary = research.get("summary", {})
            source = research.get("source", "")

            if not program_id:
                raise ValueError(f"Tier 2 Research #{i+1}: missing program_id")

            if not summary or not isinstance(summary, dict):
                raise ValueError(f"Tier 2 Program {program_id}: missing or invalid 'summary' dict")

            # Check required fields in summary
            required_fields = ["quick_facts", "fit_reasoning", "application_notes"]
            for field in required_fields:
                if field not in summary or not summary[field]:
                    raise ValueError(f"Tier 2 Program {program_id}: missing '{field}' in summary")
                if not isinstance(summary[field], str) or len(summary[field].strip()) < 30:
                    raise ValueError(
                        f"Tier 2 Program {program_id}: '{field}' must be a string with at least 30 characters. "
                        f"You provided {len(summary[field].strip()) if isinstance(summary[field], str) else 0} chars."
                    )

            # Optional: validate source if provided
            if source and source not in ["llm_knowledge", "exa"]:
                raise ValueError(f"Tier 2 Program {program_id}: source must be 'llm_knowledge' or 'exa'. You provided: {source}")

            validation_results.append({
                "program_id": program_id,
                "tier": 2,
                "summary_complete": True
            })

    # v1.09: Flexible validation - allow fewer searches if LLM used own knowledge
    if total_searches > required_searches:
        raise ValueError(f"Too many Exa searches: Expected maximum {required_searches}, but you provided {total_searches}")

    return {
        "report_generated": True,
        "report_format": report_format,
        "tier1_programs": detailed_count,
        "tier2_programs": concise_count,
        "total_exa_searches_validated": total_searches,
        "validation": validation_results,
        "message": f"""
✅ All validations passed! Generate the comprehensive report now.

Report structure (v1.09):
- TIER 1: {detailed_count} programs with 3-section analysis (program features, student experience, suitability)
- TIER 2: {concise_count} programs with concise summaries (knowledge-based)
- Final section: Application strategy

Output in user's language (Chinese if they wrote in Chinese, English if English).

Focus on:
1. Program features: Unique characteristics, curriculum, faculty, specializations
2. Student experience: Learning format, intensity, culture, day-to-day experience
3. Suitability: Why this program matches the student's background, goals, and profile

DO NOT include tuition/timeline/costs (those change frequently and are not program-specific).
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
        
        # Use correct id format for ON CONFLICT to work
        usage_id = f"{user_id}_{now.year}_{now.month}"

        cursor.execute("""
            INSERT INTO mcp_usage (id, user_id, year, month, usage_count, created_at, updated_at)
            VALUES (%s, %s, %s, %s, 1, NOW(), NOW())
            ON CONFLICT (id)
            DO UPDATE SET usage_count = mcp_usage.usage_count + 1, updated_at = NOW()
        """, (usage_id, user_id, now.year, now.month))
        
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
