#!/usr/bin/env python3
"""
OfferI MCP Server - Workflow Orchestration Version 1.08

Architecture: Token-based workflow enforcement with strict batch processing
- Each workflow tool returns a token required by the next tool
- Tools 3-5 form a batch cycle: process ONE batch → next batch
- LLM cannot skip steps or accumulate batches (enforced via tokens)

Major Changes (v1.08):
- Tool 5: Refined to per-program search with skip optimization
  * Search granularity: ONE search PER PROGRAM (not per university)
  * Query pattern: "[University] [Program Name] target audience ideal candidates background requirements"
  * Results per program: 3-8 (small focused searches)
  * Skip optimization: LLM can skip search if it already knows the program's target audience
    - Mark "skipped": true and provide "known_info" instead
    - Reduces unnecessary searches for well-known programs
  * Parameter structure:
    - "program_searches": {prog_id: {"program_name": "...", "search": {...}}}
    - Tracks searches and skips per program
  * Cost: Variable based on LLM's knowledge (more skips = lower cost)

Previous Changes (v1.07):
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
__version__ = "1.08"

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
    exploration_token: str,
    all_selected_universities: Optional[List[str]] = None,
    previous_programs_token: Optional[str] = None
) -> dict:
    """
    Step 3: Get ALL programs for EACH selected university

    Args:
        universities: List of university names for THIS batch (max 5)
        exploration_token: From explore_universities()
        all_selected_universities: REQUIRED on first batch - complete list of ALL universities you plan to process
        previous_programs_token: For 2nd+ batches - token from previous get_university_programs() call

    Returns:
        programs_token + all programs grouped by university

    🔄 BATCH WORKFLOW (for >5 universities):

    Example: You selected 12 universities total

    Batch 1 (first call):
    get_university_programs(
        universities=["CMU", "Stanford", "MIT", "Berkeley", "Cornell"],  # First 5
        exploration_token="...",
        all_selected_universities=["CMU", "Stanford", "MIT", "Berkeley", "Cornell",
                                   "UW", "GT", "UMich", "UCI", "Syracuse", "UT Austin", "UMD"]  # ALL 12
    )

    Batch 2 (second call):
    get_university_programs(
        universities=["UW", "GT", "UMich", "UCI", "Syracuse"],  # Next 5
        exploration_token="...",
        previous_programs_token="programs_xxx"  # From batch 1
    )

    Batch 3 (final):
    get_university_programs(
        universities=["UT Austin", "UMD"],  # Remaining 2
        exploration_token="...",
        previous_programs_token="programs_yyy"  # From batch 2
    )

    Note: System will guide you on batch processing if needed
    """
    exploration_data = validate_token(exploration_token, "exploration")
    career_clarity = exploration_data.get("career_clarity", "medium")

    if not universities or not isinstance(universities, list):
        raise ValueError("You must provide a list of university names")

    # Determine total selected universities list
    total_selected_unis = None
    cumulative_programs = {}
    cumulative_unis_processed = []

    if previous_programs_token:
        # Batch 2+: inherit from previous batch
        previous_data = validate_token(previous_programs_token, "programs")
        total_selected_unis = previous_data.get("total_selected_universities")
        cumulative_programs = previous_data.get("cumulative_all_programs", {})
        cumulative_unis_processed = previous_data.get("cumulative_universities_processed", [])

        if not total_selected_unis:
            raise ValueError(
                "Previous programs_token is missing total_selected_universities.\n"
                "This shouldn't happen - please report this error."
            )
    else:
        # Batch 1: must provide all_selected_universities
        if not all_selected_universities:
            raise ValueError(
                "⚠️ FIRST BATCH REQUIREMENT:\n\n"
                "On the first call to get_university_programs(), you MUST provide 'all_selected_universities' parameter.\n\n"
                "This should be the COMPLETE list of ALL universities you plan to process (not just the first 5).\n\n"
                "Example:\n"
                "get_university_programs(\n"
                "    universities=['CMU', 'Stanford', 'MIT', 'Berkeley', 'Cornell'],  # First batch (5)\n"
                "    exploration_token='...',\n"
                "    all_selected_universities=['CMU', 'Stanford', 'MIT', 'Berkeley', 'Cornell',\n"
                "                               'UW', 'GT', 'UMich', 'UCI', 'Syracuse', 'UT Austin', 'UMD']  # ALL 12\n"
                ")"
            )

        if not isinstance(all_selected_universities, list):
            raise ValueError("all_selected_universities must be a list")

        total_selected_unis = all_selected_universities

    # Validate current batch universities are in total list
    invalid_unis = [uni for uni in universities if uni not in total_selected_unis]
    if invalid_unis:
        raise ValueError(
            f"Invalid universities in current batch: {invalid_unis}\n\n"
            f"These universities are not in your all_selected_universities list.\n"
            f"Total selected: {total_selected_unis}"
        )

    # Check for duplicates
    already_processed = set(cumulative_unis_processed)
    duplicates = set(universities) & already_processed
    if duplicates:
        raise ValueError(
            f"Universities already processed in previous batch: {duplicates}\n\n"
            f"Previously processed: {cumulative_unis_processed}\n"
            f"Remaining to process: {sorted(set(total_selected_unis) - already_processed)}"
        )

    # Enforce batch size limit to avoid token overflow
    if len(universities) > 5:
        # Provide helpful batch processing guidance
        total = len(universities)
        batches = (total + 4) // 5  # Ceiling division
        first_batch = universities[:5]
        remaining = universities[5:]

        suggestion = f"Batch 1: {first_batch}\n"
        if len(remaining) <= 5:
            suggestion += f"Batch 2: {remaining}"
        else:
            suggestion += f"Batch 2-{batches}: Process {len(remaining)} remaining universities in groups of 5"

        raise ValueError(
            f"⚠️ Batch Size Limit: You provided {total} universities, but this tool handles max 5 per call.\n\n"
            f"💡 Solution: Process in {batches} batches of ≤5 universities each.\n\n"
            f"Suggested batching:\n{suggestion}\n\n"
            f"After each batch, accumulate the programs_tokens before proceeding to screening."
        )

    all_programs = {}
    total_programs = 0

    for uni in universities:
        programs = _search_programs(uni)
        if programs:
            all_programs[uni] = programs
            total_programs += len(programs)

    # Accumulate with previous batches
    cumulative_all_programs = {**cumulative_programs, **all_programs}
    cumulative_universities_processed = cumulative_unis_processed + universities
    cumulative_total_programs = sum(len(progs) for progs in cumulative_all_programs.values())

    # Check if all universities have been processed
    remaining_unis = set(total_selected_unis) - set(cumulative_universities_processed)
    is_complete = len(remaining_unis) == 0

    token = generate_token("programs", {
        "universities": universities,
        "all_programs": all_programs,
        "total_programs": total_programs,
        "career_clarity": career_clarity,
        "total_selected_universities": total_selected_unis,
        "cumulative_universities_processed": cumulative_universities_processed,
        "cumulative_all_programs": cumulative_all_programs,
        "is_complete": is_complete
    })

    completion_status = "✅ ALL BATCHES COMPLETE" if is_complete else f"⏳ IN PROGRESS - {len(remaining_unis)} universities remaining"

    return {
        "programs_token": token,
        "programs_by_university": all_programs,
        "total_programs": total_programs,
        "universities_count": len(all_programs),
        "batch_number": len(cumulative_universities_processed) // 5 + (1 if len(cumulative_universities_processed) % 5 else 0),
        "total_selected_universities": len(total_selected_unis),
        "cumulative_universities_processed": len(cumulative_universities_processed),
        "remaining_universities": list(remaining_unis),
        "is_complete": is_complete,
        "completion_status": completion_status,
        "instructions": f"""
✅ Batch complete! Progress: {len(cumulative_universities_processed)}/{len(total_selected_unis)} universities processed.

{completion_status}

{f'''📋 NEXT BATCH REQUIRED:
- Call get_university_programs() again with remaining {len(remaining_unis)} universities
- Include previous_programs_token="{token}"
- Remaining: {sorted(remaining_unis)}
''' if not is_complete else '''✅ ALL UNIVERSITIES PROCESSED!
- Proceed to TWO-PASS screening (shortlist_programs_by_name)
- Use the programs_token from this response'''}

⚠️ BATCH PROCESSING GUIDANCE:
- This tool can handle 5 universities per call (to avoid 25k token response limit)
- After all batches complete, proceed to TWO-PASS screening across ALL programs

CRITICAL: Perform TWO-PASS screening to ensure quality and reduce web search load.

PASS 1 - Remove Obvious Mismatches (排除法):
- Review ALL program names carefully across all batches
- Remove programs that are OBVIOUSLY unrelated to student's field/interests
- Examples of obvious mismatches: Architecture for CS student, Pure Arts for Engineering student,
  Biology for Business student, Humanities for Tech student
- Only remove programs that are clearly in completely different domains
- Philosophy: 宁少不多 (remove clear mismatches, but don't be overly aggressive)

PASS 2 - Select Relevant Programs (选择法):
- Review remaining programs from Pass 1
- Positively SELECT programs that match student's background and interests
- Consider: Student's major, internships, career goals, skills
- Include borderline cases (they will be validated in next steps)
- Goal: From the remaining pool, select programs with reasonable fit

Submit ONLY the final shortlist after both passes to shortlist_programs_by_name().

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
    Step 4: Shortlist programs by name analysis (BATCH PROCESSING)

    ⚠️ WORKFLOW: Process ONE batch at a time
    - This tool processes programs from ONE get_university_programs() call
    - After shortlisting, immediately proceed to validate_programs_with_web() for THIS batch
    - Then move to next batch: Tool 3 → Tool 4 → Tool 5 → repeat
    - System tracks total selected universities to ensure ALL batches complete before scoring

    🔄 BATCH TRACKING (v1.14):
    - Tool 3 records total_selected_universities on first call
    - This list propagates through all tokens (programs → shortlist → validation)
    - Tool 5 checks if ALL universities validated before marking is_complete=True
    - Tool 6 enforces is_complete=True before allowing scoring/ranking

    TWO-PASS SCREENING (for this batch):
    PASS 1 - Remove Obvious Mismatches (排除法): Eliminate programs in completely different domains
    PASS 2 - Select Relevant Programs (选择法): From remaining programs, positively select those matching student profile

    Args:
        shortlisted_by_university: Dict mapping university name to list of program IDs
            Example: {
                "CMU": [123, 456, 789],
                "Stanford": [234, 567],
                ...
            }
        programs_token: From get_university_programs() for THIS batch

    Returns:
        shortlist_token + statistics + instructions for immediate Tool 5 call
    """
    programs_data = validate_token(programs_token, "programs")
    career_clarity = programs_data.get("career_clarity", "medium")
    total_selected_unis = programs_data.get("total_selected_universities", [])

    if not shortlisted_by_university or not isinstance(shortlisted_by_university, dict):
        raise ValueError("You must provide shortlisted_by_university as a dict")

    total_shortlisted = sum(len(ids) for ids in shortlisted_by_university.values())

    if total_shortlisted == 0:
        raise ValueError("You must shortlist at least some programs. Did you review the program names?")

    token = generate_token("shortlist", {
        "universities": list(shortlisted_by_university.keys()),
        "shortlisted_by_university": shortlisted_by_university,
        "total_shortlisted": total_shortlisted,
        "career_clarity": career_clarity,
        "total_selected_universities": total_selected_unis
    })
    
    university_names = list(shortlisted_by_university.keys())

    return {
        "shortlist_token": token,
        "shortlisted_by_university": shortlisted_by_university,
        "total_shortlisted": total_shortlisted,
        "universities_count": len(shortlisted_by_university),
        "university_names_for_validation": university_names,
        "instructions": f"""
✅ BATCH SHORTLIST COMPLETE: {total_shortlisted} programs from {len(shortlisted_by_university)} universities

⚠️ IMMEDIATE NEXT STEP: Perform THIRD-ROUND filtering, then web search, then proceed to Tool 5

📋 THIRD-ROUND FILTERING (严格筛选):
Based on career_clarity and student background, aggressively filter programs:

If career_clarity = "high" (目标清晰):
→ STRICTLY remove programs that DON'T match student's stated career direction
→ Only keep programs DIRECTLY aligned with career goals
→ Example: Student targets research → Remove professional/industry-focused programs
→ Be aggressive: 宁缺毋滥 (better to have fewer perfect matches)

If career_clarity = "low" (看重学校牌子):
→ Remove programs from lower-tier universities
→ Keep only top-reputation schools
→ Less strict on program fit, more strict on university reputation

If career_clarity = "medium":
→ Balanced filtering: remove obvious mismatches but keep borderline cases
→ Consider both program fit AND university reputation

After third-round filtering for ALL universities in this batch:
→ For EACH remaining program, perform ONE web search
→ Query pattern: "[University] [Program Name] target audience ideal candidates background requirements"
→ Focus: What kind of students is THIS SPECIFIC PROGRAM looking for?

⚠️ OPTIMIZATION: Skip search if you already know the program well
- If your knowledge base has clear information about this program's target audience
- You can mark it as "skipped": true and provide "known_info" instead
- Only search if you're uncertain about the target audience

→ Then perform FOURTH-ROUND (final) filtering based on search results and known info

Call validate_programs_with_web(program_validations, shortlist_token)
DO NOT wait for other batches. Process one batch at a time: Tool 3 → Tool 4 → Tool 5 → repeat.
        """,
        "next_step": "Call validate_programs_with_web(web_validations, shortlist_token)"
    }


@mcp.tool
async def validate_programs_with_web(
    web_validations: Dict[str, dict],
    shortlist_token: str,
    previous_validation_token: Optional[str] = None
) -> dict:
    """
    Step 5: Four-round filtering workflow with target audience validation

    🔄 BATCH PROCESSING (Coordinated with Tool 4):
    - Each Tool 4 call creates a shortlist_token for one batch
    - Call THIS tool immediately after Tool 4 to validate that batch
    - Use previous_validation_token to chain multiple batches
    - System enforces ALL universities validated before proceeding to Tool 6

    📋 FOUR-ROUND FILTERING WORKFLOW (per batch):

    Round 3 - Career-Clarity-Based Strict Filtering:
    YOU must perform this filtering BEFORE calling this tool.

    If career_clarity = "high" (目标清晰):
    - STRICTLY remove programs that DON'T match student's stated career direction
    - Only keep programs DIRECTLY aligned with career goals
    - Philosophy: 宁缺毋滥 (better fewer perfect matches than many mediocre ones)

    If career_clarity = "low" (看重学校牌子):
    - Remove programs from lower-tier universities
    - Keep only top-reputation schools
    - Less strict on program fit, more strict on university reputation

    If career_clarity = "medium":
    - Balanced: remove obvious mismatches, keep borderline cases
    - Consider both fit AND reputation

    Web Search - Per-Program Target Audience Validation:
    After Round 3 filtering, for EACH remaining program:
    - Query pattern: "[University] [Program Name] target audience ideal candidates background requirements"
    - Purpose: Understand what kind of students THIS SPECIFIC PROGRAM is looking for
    - Results: 3-8 recommended per program (small focused searches)
    - Use your built-in web search capability

    ⚠️ OPTIMIZATION: Skip search if you already know the program
    - If your knowledge base has clear info about this program's target audience
    - Mark as "skipped": true and provide "known_info" instead of search results
    - Only search if you're uncertain

    Round 4 - Final Filtering:
    YOU must perform this filtering based on search results and known info.
    - Match user background against each program's target audience
    - Remove programs seeking very different candidate profiles
    - Keep programs that match user's strengths

    Args:
        web_validations: Dict mapping university name to validation data
            Keys must be from shortlist_programs_by_name (you can validate a subset)

            ✨ v1.11 Simplified Structure (reduced required fields from 5 → 2):

            Example: {
                "University Name": {
                    "third_round_program_ids": [123, 456, 789],  # Required: After Round 3 career-based filtering
                    "program_searches": {
                        "123": {  # program_id as string (JSON requirement)
                            "program_name": "MISM",  # ✅ OPTIONAL: Auto-filled from database if omitted
                            "search": {
                                "skipped": false,  # ✅ REQUIRED
                                "query": "CMU MISM target audience ideal candidates...",  # ✅ REQUIRED (if not skipped)
                                "num_results": 5,  # ✅ OPTIONAL: Auto-defaults to 5 (range 3-8)
                                "findings": "..."  # Your search results
                            }
                        },
                        "456": {
                            "program_name": "MSCS",  # ✅ OPTIONAL
                            "search": {
                                "skipped": true,  # ✅ REQUIRED
                                "known_info": "Targets students with strong CS background..."  # ✅ OPTIONAL: Auto-generated if omitted
                            }
                        }
                    },
                    "final_program_ids": [123, 456]  # Required: After Round 4 final filtering
                },
                ...
            }

            📝 Field Summary:
            - program_name: Optional (auto-filled from database)
            - skipped: Required (boolean)
            - query: Required if skipped=false
            - num_results: Optional (defaults to 5)
            - known_info: Optional if skipped=true (auto-generated)

            ⚠️ Error Reporting: All validation errors returned at once (batch mode)

        shortlist_token: From shortlist_programs_by_name() for THIS batch
        previous_validation_token: From previous validate_programs_with_web() call (if not first batch)

    Returns:
        validation_token + batch completion status + next_step instructions
    """
    shortlist_data = validate_token(shortlist_token, "shortlist")
    career_clarity = shortlist_data.get("career_clarity", "medium")

    if not web_validations or not isinstance(web_validations, dict):
        raise ValueError("You must provide web_validations as a dict")

    # v1.14: Use total_selected_universities instead of current batch universities
    # This fixes the bug where LLM could finish with just one batch
    expected_unis = shortlist_data.get("total_selected_universities", shortlist_data["universities"])

    # Fallback for backwards compatibility (if old tokens don't have total_selected_universities)
    if not expected_unis:
        expected_unis = shortlist_data["universities"]

    # Get previously validated universities (for batch processing)
    previously_validated = set()
    previous_program_ids = []
    previous_validations = {}
    previous_career_clarity = career_clarity  # Default to current

    if previous_validation_token:
        previous_data = validate_token(previous_validation_token, "validation")
        previously_validated = set(previous_data.get("validated_universities", []))
        previous_program_ids = previous_data.get("final_program_ids", [])
        previous_validations = previous_data.get("web_validations", {})
        previous_career_clarity = previous_data.get("career_clarity", career_clarity)

    # Check for duplicate validations
    current_unis = set(web_validations.keys())
    duplicates = current_unis & previously_validated
    if duplicates:
        raise ValueError(
            f"Universities already validated in previous batch: {duplicates}\n\n"
            f"You cannot validate the same university twice.\n"
            f"Previously validated: {sorted(previously_validated)}\n"
            f"Universities you can still validate: {sorted(set(expected_unis) - previously_validated)}"
        )

    # BATCH PROCESSING: Only validate that provided universities are valid
    invalid_unis = [uni for uni in web_validations.keys() if uni not in expected_unis]
    if invalid_unis:
        raise ValueError(
            f"Invalid university names: {invalid_unis}\n\n"
            f"These universities were not in your shortlist.\n"
            f"Valid university names: {expected_unis}\n\n"
            f"Tip: Copy exact names from shortlist_programs_by_name response."
        )

    # Validate each university's four-round filtering
    # v1.11: Collect all errors instead of failing immediately (batch error reporting)
    all_final_ids = []
    total_searches = 0
    total_skipped = 0
    errors = []

    # Get all program IDs to fetch names from database
    all_prog_ids = set()
    for validation in web_validations.values():
        third_round_ids = validation.get("third_round_program_ids", [])
        all_prog_ids.update(third_round_ids)

    # Fetch program names from database for auto-fill
    program_info_map = {}
    if all_prog_ids:
        program_details = _get_program_details_batch(list(all_prog_ids))
        program_info_map = {p["program_id"]: p["program_name"] for p in program_details}

    for uni, validation in web_validations.items():
        if not isinstance(validation, dict):
            errors.append(f"• {uni}: validation must be a dict")
            continue

        # Validate Round 3 - Career-based filtering results
        if "third_round_program_ids" not in validation:
            errors.append(f"• {uni}: missing 'third_round_program_ids' (after career-clarity-based filtering)")
            continue

        third_round_ids = validation["third_round_program_ids"]
        if not isinstance(third_round_ids, list):
            errors.append(f"• {uni}: third_round_program_ids must be a list")
            continue

        # Validate per-program searches
        if "program_searches" not in validation:
            errors.append(f"• {uni}: missing 'program_searches' (per-program target audience validation)")
            continue

        program_searches = validation["program_searches"]
        if not isinstance(program_searches, dict):
            errors.append(f"• {uni}: program_searches must be a dict")
            continue

        # Check each program in third_round has a search entry
        for prog_id in third_round_ids:
            # Convert to string because JSON object keys are always strings
            prog_id_str = str(prog_id)
            if prog_id_str not in program_searches:
                errors.append(f"• {uni}: program {prog_id} passed Round 3 but has no search entry in program_searches")
                continue

            prog_search = program_searches[prog_id_str]
            if not isinstance(prog_search, dict):
                errors.append(f"• {uni}: program {prog_id} search entry must be a dict")
                continue

            # v1.11: Auto-fill program_name from database if not provided
            if "program_name" not in prog_search or not prog_search["program_name"]:
                prog_name = program_info_map.get(prog_id, f"Program {prog_id}")
                prog_search["program_name"] = prog_name

            if "search" not in prog_search:
                errors.append(f"• {uni}: program {prog_id} missing 'search' field")
                continue

            search = prog_search["search"]
            if not isinstance(search, dict):
                errors.append(f"• {uni}: program {prog_id} search must be a dict")
                continue

            if "skipped" not in search:
                errors.append(f"• {uni}: program {prog_id} search missing 'skipped' field")
                continue

            if search["skipped"]:
                # v1.11: Auto-generate known_info if not provided
                if "known_info" not in search or not search["known_info"]:
                    prog_name = prog_search.get("program_name", f"Program {prog_id}")
                    search["known_info"] = f"Program validated based on general knowledge of {prog_name}"
                total_skipped += 1
            else:
                # Actual search - must have query
                if "query" not in search:
                    errors.append(f"• {uni}: program {prog_id} search missing 'query' field (required when not skipped)")
                    continue

                # v1.11: Auto-default num_results to 5 if not provided
                if "num_results" not in search:
                    search["num_results"] = 5
                elif not (3 <= search["num_results"] <= 8):
                    errors.append(f"• {uni}: program {prog_id} search num_results must be 3-8 (you provided {search['num_results']})")
                    continue

                total_searches += 1

        # Validate Round 4 - Final filtering results
        if "final_program_ids" not in validation:
            errors.append(f"• {uni}: missing 'final_program_ids' (after Round 4 final filtering)")
            continue

        final_ids = validation["final_program_ids"]
        if not isinstance(final_ids, list):
            errors.append(f"• {uni}: final_program_ids must be a list")
            continue

        all_final_ids.extend(final_ids)

    # If any errors were collected, raise them all at once
    if errors:
        error_msg = f"Found {len(errors)} validation error(s):\n\n" + "\n".join(errors)
        error_msg += "\n\n💡 Tip: Fix all errors listed above and retry."
        raise ValueError(error_msg)

    if len(all_final_ids) == 0:
        raise ValueError("No programs passed validation. Did you filter too aggressively?")

    # Accumulate validated universities and program IDs
    cumulative_validated = list(previously_validated) + list(current_unis)
    cumulative_program_ids = previous_program_ids + all_final_ids
    cumulative_validations = {**previous_validations, **web_validations}

    # Check completion status
    remaining_unis = set(expected_unis) - set(cumulative_validated)
    is_complete = len(remaining_unis) == 0

    token = generate_token("validation", {
        "validated_universities": cumulative_validated,
        "total_universities_validated": len(cumulative_validated),
        "expected_universities": expected_unis,
        "remaining_universities": list(remaining_unis),
        "is_complete": is_complete,
        "web_searches_completed": total_searches,
        "final_program_ids": cumulative_program_ids,
        "web_validations": cumulative_validations,
        "career_clarity": career_clarity
    })

    completion_status = "✅ COMPLETE - All universities validated!" if is_complete else f"⏳ IN PROGRESS - {len(remaining_unis)} universities remaining"

    return {
        "validation_token": token,
        "batch_universities_validated": len(web_validations),
        "total_universities_validated": len(cumulative_validated),
        "expected_total": len(expected_unis),
        "remaining_universities": list(remaining_unis),
        "is_complete": is_complete,
        "completion_status": completion_status,
        "total_web_searches": total_searches,
        "total_skipped_searches": total_skipped,
        "batch_programs_count": len(all_final_ids),
        "cumulative_programs_count": len(cumulative_program_ids),
        "message": f"✅ Batch validated {len(web_validations)} universities with {total_searches} web searches ({total_skipped} programs skipped using known info)\n{completion_status}",
        "instructions": f"""
This batch is validated. Progress: {len(cumulative_validated)}/{len(expected_unis)} universities complete.

{"📋 NEXT BATCH REQUIRED:" if not is_complete else "✅ ALL UNIVERSITIES VALIDATED!"}
{f'''- Call validate_programs_with_web() again with remaining universities
- Include previous_validation_token="{token}"
- Remaining: {remaining_unis}''' if not is_complete else "- Proceed to score_and_rank_programs(validation_token)"}

⚠️ IMPORTANT: You CANNOT proceed to scoring until is_complete=True
        """,
        "next_step": "Validate remaining universities" if not is_complete else "Call score_and_rank_programs(validation_token)"
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
    career_clarity = validation_data.get("career_clarity", "medium")

    # Enforce completion requirement
    if not validation_data.get("is_complete", False):
        remaining = validation_data.get("remaining_universities", [])
        validated = validation_data.get("validated_universities", [])
        expected = validation_data.get("expected_universities", [])
        raise ValueError(
            f"❌ VALIDATION INCOMPLETE!\n\n"
            f"You have NOT validated all universities from your shortlist.\n\n"
            f"Progress: {len(validated)}/{len(expected)} universities\n"
            f"Validated: {validated}\n"
            f"Remaining: {remaining}\n\n"
            f"You MUST call validate_programs_with_exa() again for remaining universities.\n"
            f"Include previous_validation_token to continue tracking progress."
        )

    final_ids = validation_data["final_program_ids"]
    universities_count = validation_data["total_universities_validated"]

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
        required_searches = 30  # Tier 1 only: 10 programs × 3 searches = 30
    else:
        report_format = "TOP_10"
        detailed_count = 5   # Tier 1: Full Exa research
        concise_count = 0    # No Tier 2 for small selection
        required_searches = 15  # 5 programs × 3 searches = 15

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

📋 TWO-TIER RESEARCH WORKFLOW:

TIER 1 (Detailed Research) - {detailed_count} programs:
- MUST perform 3 Exa searches per program (tuition/features/deadline)
- MUST provide full 6-dimension analysis
- Total: {required_searches} Exa searches required

TIER 2 (Concise Summary) - {concise_count} programs:
- NO Exa searches required (use your knowledge base up to Jan 2025)
- Provide concise summary with 3 fields:
  * quick_facts: Basic info (tuition range, duration, format)
  * fit_reasoning: Why recommend for this student
  * application_notes: Key application points
- Source: mark as "llm_knowledge"

🎯 Tier 1 Search Strategy:
1. FIRST: Try Exa MCP (mcp__exa__web_search_exa) for each search
2. IF Exa returns no useful results: Use your own knowledge
3. ALWAYS fill "findings" field with detailed content (min 50 chars)

For EACH of the top {detailed_count} programs (Tier 1), do EXACTLY 3 Exa searches:

🔍 Search 1: Tuition & Living Cost (4 results required)
Query: "[University] [Program] tuition fees living cost total expense 2025"

Recommended Exa MCP Parameters:
mcp__exa__web_search_exa(
    query="<constructed query>",
    numResults=4,
    useAutoprompt=true,
    searchType="auto",
    startPublishedDate="2025-01-01",  # MUST be 2025 for current tuition!
    includeDomains=["<university_domain>.edu"],  # ⚠️ Use specific university domain
    useHighlights=true,               # ⚠️ CRITICAL: Reduce tokens
    highlightNumSentences=5,
    highlightPerUrl=4
)

Then fill findings field:
- If Exa found info: "findings": "Based on Exa search: Tuition $X, living $Y, total ~$Z..."
- If Exa failed: "findings": "Exa returned no results. Based on general knowledge: Typical range $X-Y..."

🔍 Search 2: Program Features & Career Outlook (8 results required)
Query: "[University] [Program] curriculum faculty career outcomes alumni reviews"

Exa MCP Parameters:
mcp__exa__web_search_exa(
    query="<constructed query>",
    numResults=8,
    useAutoprompt=true,
    searchType="auto",
    useHighlights=true,               # ⚠️ CRITICAL: Reduce tokens
    highlightNumSentences=8,
    highlightPerUrl=6
    # NO includeDomains - need both official info and real student reviews!
)

Then fill findings field:
- If Exa found info: "findings": "Based on Exa search: Core courses include X, Y. 95% employment rate..."
- If Exa failed: "findings": "Exa returned limited results. Based on general knowledge: Program focuses on..."

🔍 Search 3: Application Deadlines & Requirements (4 results required)
Query: "[University] [Program] admissions deadline [month keywords] [year]"
      ⚠️ Use SPECIFIC keywords: include deadline months and application year
      Example: "Carnegie Mellon MISM admissions deadline December January 2026"

Recommended Exa MCP Parameters:
mcp__exa__web_search_exa(
    query="<constructed query>",
    numResults=4,
    useAutoprompt=true,
    searchType="auto",
    startPublishedDate="2025-01-01",  # MUST be 2025 for current deadlines!
    includeDomains=["<university_domain>.edu"],  # ⚠️ Use specific university domain
    useHighlights=true,               # ⚠️ CRITICAL: Reduce tokens
    highlightNumSentences=5,
    highlightPerUrl=3
)

Then fill findings field:
- If Exa found info: "findings": "Based on Exa search: Round 1 deadline Jan 5, Round 2 Mar 15..."
- If Exa failed: "findings": "Exa found no specific dates. Based on general knowledge: Typically early January..."

Total: 4 + 8 + 4 = 16 results per program ({detailed_count} programs × 16 = {required_searches} searches)

Work systematically:
1. Complete all Tier 1 programs (3 searches each): Program #1 → #2 → ... → #{detailed_count}
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
    Step 7: Generate comprehensive two-tier report (v1.15)

    Args:
        detailed_program_research: Tier 1 programs with full Exa research
            Each: {
                "program_id": 123,
                "exa_searches": [
                    {
                        "query": "CMU MISM tuition fees living cost 2025",
                        "num_results": 4,
                        "findings": "Based on Exa search: Total cost ~$85k (tuition $70k + living $15k)...",
                        "source": "exa"  # Optional: "exa" or "llm_knowledge"
                    },
                    {
                        "query": "CMU MISM curriculum faculty career outcomes",
                        "num_results": 8,
                        "findings": "Based on Exa search: Strong analytics focus, 95% employment rate...",
                        "source": "exa"
                    },
                    {
                        "query": "CMU MISM admissions deadline January 2026",
                        "num_results": 4,
                        "findings": "Could not find via Exa. Based on general knowledge: Typically Jan 5...",
                        "source": "llm_knowledge"  # Use when Exa fails
                    }
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

        ⚠️ CRITICAL: "findings" field is REQUIRED and MUST be non-empty (min 50 chars)
        - First try Exa MCP search (mcp__exa__web_search_exa)
        - If Exa returns no useful results, use your own knowledge and mark source="llm_knowledge"
        - NEVER submit empty findings or skip this field

        concise_program_research: Tier 2 programs with concise summaries (TOP_20 format only)
            Each: {
                "program_id": 456,
                "summary": {
                    "quick_facts": "1-year MS, ~$60k total cost, STEM-designated, evening classes available",
                    "fit_reasoning": "Strong PM training with tech emphasis, matches Google PM experience. Industry partnerships for capstone projects.",
                    "application_notes": "Round 1 deadline typically Jan 5, requires PM portfolio or work samples, GRE optional, 3.0+ GPA recommended"
                },
                "source": "llm_knowledge"
            }

        ⚠️ TIER 2 REQUIREMENTS (v1.15):
        - Required when report_format="TOP_20" (≥7 universities selected)
        - NO Exa searches needed - use your knowledge base
        - Each field in summary must be ≥30 characters
        - quick_facts: Basic program facts (cost, duration, format)
        - fit_reasoning: Why suitable for this student's profile
        - application_notes: Key application requirements and deadlines

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
        
        if len(exa_searches) != 3:
            raise ValueError(f"Program {program_id}: must have EXACTLY 3 Exa searches. You provided {len(exa_searches)}.")

        # Validate each search with specific result count requirements
        expected_results = [4, 8, 4]
        search_names = ["Tuition & Cost", "Program Features & Career", "Application Deadline"]

        for j, search in enumerate(exa_searches):
            if not isinstance(search, dict):
                raise ValueError(f"Program {program_id}, Search #{j+1} ({search_names[j]}): must be a dict")

            # Validate num_results
            if "num_results" not in search:
                raise ValueError(f"Program {program_id}, Search #{j+1} ({search_names[j]}): missing 'num_results' field")

            expected = expected_results[j]
            actual = search["num_results"]

            if actual != expected:
                raise ValueError(
                    f"Program {program_id}, Search #{j+1} ({search_names[j]}): "
                    f"must have EXACTLY {expected} results. You provided {actual}"
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
        
        required_dims = ["location_environment", "career_prospects", "program_intensity", 
                        "unique_features", "application_timeline", "total_cost"]
        missing_dims = [dim for dim in required_dims if dim not in dimensions]
        if missing_dims:
            raise ValueError(f"Program {program_id}: missing dimensions: {missing_dims}")
        
        validation_results.append({
            "program_id": program_id,
            "tier": 1,
            "exa_searches_count": len(exa_searches),
            "dimensions_complete": True
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

    if total_searches != required_searches:
        raise ValueError(f"Expected {required_searches} total Exa searches for Tier 1, but you provided {total_searches}")
    
    return {
        "report_generated": True,
        "report_format": report_format,
        "tier1_programs": detailed_count,
        "tier2_programs": concise_count,  # v1.15: Fixed to use concise_count
        "total_exa_searches_validated": total_searches,
        "validation": validation_results,
        "message": f"""
✅ All validations passed! Generate the comprehensive report now.

Report structure (v1.15):
- TIER 1: {detailed_count} programs with full 6-dimension profiles (Exa-researched)
- TIER 2: {concise_count} programs with concise summaries (knowledge-based)
- Final section: Application strategy

Output in user's language (Chinese if they wrote in Chinese).

Include specific details from Exa searches for Tier 1 programs (tuition, deadlines, features).
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
