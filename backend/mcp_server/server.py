#!/usr/bin/env python3
"""
OfferI MCP Server v1.2.0

Database: 44,352 programs from 1,160 universities worldwide.
Token-based workflow with 6-step orchestration.

Transport:
- STDIO: Internal workers (default)
- HTTP: External users via --http flag
"""
import os
import sys
import sqlite3
import secrets
import json
import psycopg2
from pathlib import Path
from typing import Optional, List, Any, Dict, Union
from datetime import datetime
from fastmcp import FastMCP

# Version
__version__ = "1.2.0"

# Database path
DB_PATH = os.getenv("DB_PATH", "/app/mcp/programs.db")

# Classification mapping (15 categories)
CLASSIFICATIONS = {
    1: "Health Sciences & Medicine",
    2: "Business & Management",
    3: "Engineering",
    4: "Social Sciences",
    5: "Education",
    6: "Humanities & Languages",
    7: "Arts Media & Design",
    8: "Computing & Data Science",
    9: "Physical & Mathematical Sciences",
    10: "Law & Public Policy",
    11: "Life Sciences",
    12: "Finance & Economics",
    13: "Architecture & Planning",
    14: "Environment & Sustainability",
    15: "Interdisciplinary Studies"
}

# In-memory token store (for validation)
_active_tokens = {}

# Initialize FastMCP server
mcp = FastMCP(
    name="OfferI Study Abroad",
    instructions="""
    Study abroad consultation server with 44,352 programs from 1,160 universities.

    6-step workflow (token-based):
    1. start_and_select_universities - Select universities with strategy
    2. select_classifications - Choose academic fields
    3. process_university_programs - University-by-university program filtering
    4. analyze_and_shortlist - Research and shortlist per university
    5. select_final_programs - Choose final programs by strategy ratio
    6. generate_final_report - Generate recommendations

    Output language matches user input.
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


def validate_api_key_and_tool(tool_name: str) -> tuple:
    """
    Validate API key and check tool permission based on tier.

    Extracts API key from HTTP Authorization header or SSE_API_KEY env var,
    queries PostgreSQL for tier and allowed_tools, and validates access.

    Args:
        tool_name: Name of the tool being called

    Returns:
        (tier, allowed_tools) if valid

    Raises:
        ValueError: If API key is invalid, inactive, or lacks permission
    """
    from fastmcp.server.dependencies import get_http_headers

    # Extract API key from Authorization header or environment
    api_key = ""
    try:
        headers = get_http_headers()
        auth_header = headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
    except:
        pass  # Exception during header retrieval

    # Fallback to environment variable if no API key from headers
    if not api_key:
        api_key = os.getenv("SSE_API_KEY", "")

    if not api_key or not api_key.startswith("sk_"):
        raise ValueError("Invalid or missing API key. Please provide a valid API key in Authorization header.")

    # Query PostgreSQL for tier and allowed_tools
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            dbname=os.getenv("POSTGRES_DB", "offeri"),
            user=os.getenv("POSTGRES_USER", "offeri_user"),
            password=os.getenv("POSTGRES_PASSWORD", "")
        )
        cursor = conn.cursor()

        cursor.execute("""
            SELECT tier, allowed_tools, is_active
            FROM api_keys
            WHERE id = %s
        """, (api_key,))
        result = cursor.fetchone()

        if not result:
            conn.close()
            raise ValueError(f"API key not found or invalid: {api_key[:20]}...")

        tier, allowed_tools, is_active = result

        if not is_active:
            conn.close()
            raise ValueError(f"API key has been revoked. Please generate a new key at https://offeri.org/dashboard")

        # Validate tool permission
        if tool_name not in allowed_tools:
            conn.close()
            # Show first 5 tools to avoid overwhelming user
            available_tools = ', '.join(allowed_tools[:5])
            if len(allowed_tools) > 5:
                available_tools += f" (and {len(allowed_tools) - 5} more)"
            raise ValueError(
                f"Access denied: {tool_name}\n"
                f"Your tier '{tier}' only has access to: {available_tools}"
            )

        conn.close()
        return (tier, allowed_tools)

    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"API key validation failed (database error): {e}")


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
    """Internal: Get programs for a university, optionally filtered by classifications (OR logic for primary and secondary)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT program_id, program_name, degree_type
        FROM programs
        WHERE LOWER(university_name) LIKE LOWER(?)
    """
    params = [f"%{university_name}%"]

    if classification_filters:
        # OR logic: match if EITHER classification OR secondary_classification matches
        placeholders = ','.join('?' * len(classification_filters))
        query += f" AND (classification IN ({placeholders}) OR secondary_classification IN ({placeholders}))"
        params.extend(classification_filters)
        params.extend(classification_filters)  # Add filters twice for both conditions

    query += " ORDER BY program_name"

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    return [{
        "id": row["program_id"],
        "name": row["program_name"],
        "degree": row["degree_type"]
    } for row in results]

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
# WORKFLOW ORCHESTRATION TOOLS
# ═══════════════════════════════════════════════════════════════

@mcp.tool
async def start_and_select_universities(
    background: str,
    country: str,
    strategy: str,
    selected_universities: Optional[List[str]] = None,
    optional_web_searches: Optional[List[dict]] = None
) -> dict:
    """
    Start consultation and select universities with strategy.

    Two-call workflow: Call 1 explores all universities in country, Call 2 submits selection.

    Args:
        background: Student profile (GPA, major, goals, experience)
        country: Target country (e.g., "USA", "UK", "Hong Kong (SAR)")
        strategy: Portfolio strategy - "conservative" or "aggressive"
        selected_universities: University names list (None for Call 1, filled for Call 2)
        optional_web_searches: 0-3 web searches to verify fit (Call 2 only)

    Returns:
        Call 1: all_universities + instructions
        Call 2: selection_token + next_step
    """
    # ═══════════════════════════════════════════════════════════════
    # API KEY & TOOL PERMISSION VALIDATION
    # ═══════════════════════════════════════════════════════════════
    tier, allowed_tools = validate_api_key_and_tool("start_and_select_universities")
    # ═══════════════════════════════════════════════════════════════

    # Validate inputs
    if not background or not isinstance(background, str):
        raise ValueError("background is required and must be a string")

    if not country or not isinstance(country, str):
        raise ValueError("country is required and must be a string")

    if strategy not in ["conservative", "aggressive"]:
        raise ValueError("strategy must be 'conservative' or 'aggressive'")

    # ═══════════════════════════════════════════════════════════════
    # TYPE COERCION: Handle MCP serialization issues
    # ═══════════════════════════════════════════════════════════════
    # MCP may serialize None/empty list as strings, fix it here
    import json

    if isinstance(selected_universities, str):
        if selected_universities == "" or selected_universities.lower() == "null":
            selected_universities = None
        else:
            try:
                selected_universities = json.loads(selected_universities)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid selected_universities format: {selected_universities}")

    if isinstance(optional_web_searches, str):
        if optional_web_searches == "" or optional_web_searches.lower() == "null":
            optional_web_searches = None
        else:
            try:
                optional_web_searches = json.loads(optional_web_searches)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid optional_web_searches format: {optional_web_searches}")
    # ═══════════════════════════════════════════════════════════════

    # Get all universities in country
    all_universities = _list_universities(country)

    if not all_universities:
        available = _get_available_countries()
        countries_str = ", ".join([f"{c['country']} ({c['count']})" for c in available[:10]])
        raise ValueError(f"Country '{country}' not found. Available: {countries_str}")

    # Strategy ratios
    strategy_ratios = {
        "conservative": {"lottery": "10%", "reach": "30%", "target": "40%", "safety": "20%"},
        "aggressive": {"lottery": "20%", "reach": "50%", "target": "20%", "safety": "10%"}
    }
    ratios = strategy_ratios[strategy]

    # CALL 1: Return all universities (exploration phase)
    if not selected_universities:
        return {
            "all_universities": all_universities,
            "total_universities": len(all_universities),
            "country": country,
            "strategy": strategy,
            "instructions": f"""
COUNTRY: {country}
TOTAL UNIVERSITIES: {len(all_universities)}
STRATEGY: {strategy.upper()}

All universities in {country}:
{chr(10).join([f"  • {uni}" for uni in all_universities])}

YOUR TASK: Select universities matching student's profile (max 14)

SELECTION STRATEGY ({strategy.capitalize()}):
1. Analyze student profile (GPA, background, goals)

2. Build portfolio across difficulty levels:
   - Lottery: {ratios['lottery']} (Dream schools, extremely competitive)
   - Reach: {ratios['reach']} (Highly competitive, student slightly below average)
   - Target: {ratios['target']} (Competitive match, student fits typical profile)
   - Safety: {ratios['safety']} (Strong admission likelihood, student above average)

3. Optional: 0-3 web searches if uncertain about specific universities

NEXT STEP:
Call start_and_select_universities() AGAIN with:
- Same background, country, strategy
- selected_universities: [chosen university names]
- optional_web_searches: [...] (if needed)
            """,
            "next_step": "Call start_and_select_universities() again with selected_universities"
        }

    # CALL 2: Process selection and generate token
    if not isinstance(selected_universities, list) or len(selected_universities) == 0:
        raise ValueError("selected_universities must be a non-empty list for Call 2")

    # Validate optional searches
    search_count = 0
    if optional_web_searches:
        if not isinstance(optional_web_searches, list):
            raise ValueError("optional_web_searches must be a list")

        if len(optional_web_searches) > 3:
            raise ValueError(f"Maximum 3 web searches allowed. You provided {len(optional_web_searches)}.")

        for i, search in enumerate(optional_web_searches):
            if not isinstance(search, dict) or "query" not in search or "num_results" not in search:
                raise ValueError(f"Search #{i+1} must be a dict with 'query' and 'num_results' fields")

            num_results = search["num_results"]
            if not isinstance(num_results, int) or num_results < 1 or num_results > 25:
                raise ValueError(f"Search #{i+1}: num_results must be 1-25. You provided {num_results}")

        search_count = len(optional_web_searches)

    # Validate university count (max 14)
    university_count = len(selected_universities)
    if university_count > 14:
        raise ValueError(
            f"Too many universities: {university_count} universities.\n"
            f"Maximum 14 universities allowed to avoid context overflow. Please reduce your selection."
        )

    # Validate selected universities
    invalid_universities = [uni for uni in selected_universities if uni not in all_universities]
    if invalid_universities:
        raise ValueError(f"Invalid universities: {invalid_universities[:5]}... Please select from the provided list.")

    token = generate_token("selection", {
        "background": background,
        "country": country,
        "strategy": strategy,
        "all_universities": all_universities,
        "selected_universities": selected_universities,
        "web_searches_completed": search_count,
        "web_searches_data": optional_web_searches or []
    })

    return {
        "selection_token": token,
        "selected_universities": selected_universities,
        "university_count": len(selected_universities),
        "country": country,
        "strategy": strategy,
        "web_searches_completed": search_count,
        "instructions": f"""
University selection complete. {'Used knowledge base only.' if search_count == 0 else f'Validated with {search_count} web search(es).'}

SELECTION RESULTS:
- Country: {country}
- Strategy: {strategy.capitalize()}
- Selected universities: {len(selected_universities)}
- Total available: {len(all_universities)}

Universities selected:
{chr(10).join([f"  • {uni}" for uni in selected_universities[:20]])}
{"  ... and more" if len(selected_universities) > 20 else ""}

NEXT STEP: Select relevant classifications

Call select_classifications(selection_token) to view all 15 classification categories and choose relevant ones based on student background.
        """,
        "next_step": "Call select_classifications(selection_token)"
    }


@mcp.tool
async def select_classifications(
    selection_token: str,
    selected_classifications: Optional[List[str]] = None
) -> dict:
    """
    Select academic fields for program filtering.

    Two-call workflow: Call 1 shows all 15 classifications, Call 2 submits selection.

    Args:
        selection_token: From start_and_select_universities()
        selected_classifications: Classification names (None for Call 1, filled for Call 2)

    Returns:
        Call 1: all_classifications + instructions
        Call 2: classifications_token + next_step
    """
    # API key validation
    tier, allowed_tools = validate_api_key_and_tool("select_classifications")

    # ═══════════════════════════════════════════════════════════════
    # TYPE COERCION: Handle MCP serialization issues
    # ═══════════════════════════════════════════════════════════════
    import json
    if isinstance(selected_classifications, str):
        if selected_classifications == "" or selected_classifications.lower() == "null":
            selected_classifications = None
        else:
            try:
                selected_classifications = json.loads(selected_classifications)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid selected_classifications format: {selected_classifications}")
    # ═══════════════════════════════════════════════════════════════

    # Validate token
    selection_data = validate_token(selection_token, "selection")
    background = selection_data.get("background", "")
    strategy = selection_data.get("strategy", "conservative")
    selected_universities = selection_data.get("selected_universities", [])

    # CALL 1: Return all classifications
    if not selected_classifications:
        classification_list = [
            {"id": 1, "name": "Health Sciences & Medicine", "description": "Healthcare, nursing, public health, biomedical sciences"},
            {"id": 2, "name": "Business & Management", "description": "Business administration, management, entrepreneurship, marketing"},
            {"id": 3, "name": "Engineering", "description": "All engineering disciplines (mechanical, civil, electrical, etc.)"},
            {"id": 4, "name": "Social Sciences", "description": "Psychology, sociology, anthropology, political science, international relations"},
            {"id": 5, "name": "Education", "description": "Teaching, educational leadership, curriculum development"},
            {"id": 6, "name": "Humanities & Languages", "description": "Literature, linguistics, history, philosophy, languages"},
            {"id": 7, "name": "Arts Media & Design", "description": "Visual arts, performing arts, media, design, communication"},
            {"id": 8, "name": "Computing & Data Science", "description": "Computer science, software engineering, data science, AI/ML"},
            {"id": 9, "name": "Physical & Mathematical Sciences", "description": "Mathematics, statistics, physics, chemistry, astronomy"},
            {"id": 10, "name": "Law & Public Policy", "description": "Law, legal studies, public administration, policy analysis"},
            {"id": 11, "name": "Life Sciences", "description": "Biology, biotechnology, genetics, neuroscience, biochemistry"},
            {"id": 12, "name": "Finance & Economics", "description": "Finance, economics, accounting, financial engineering"},
            {"id": 13, "name": "Architecture & Planning", "description": "Architecture, urban planning, landscape architecture"},
            {"id": 14, "name": "Environment & Sustainability", "description": "Environmental science, sustainability, conservation, climate"},
            {"id": 15, "name": "Interdisciplinary Studies", "description": "Cross-disciplinary programs, liberal studies, general research"}
        ]

        return {
            "all_classifications": classification_list,
            "total_classifications": 15,
            "instructions": f"""
ALL 15 CLASSIFICATION CATEGORIES

{chr(10).join([f"  {c['id']:2d}. {c['name']:40s} - {c['description']}" for c in classification_list])}

YOUR TASK: Select relevant classifications based on student background

SELECTION STRATEGY:
1. PRIMARY: Direct match with student's major/field/career goals
2. SECONDARY: Related/complementary fields student might consider
3. Be inclusive but sensible - avoid obviously irrelevant fields

NEXT STEP:
Call select_classifications() AGAIN with:
- Same selection_token
- selected_classifications: [list of chosen classification names]
            """,
            "next_step": "Call select_classifications() again with selected_classifications"
        }

    # CALL 2: Process selection and generate token
    if not isinstance(selected_classifications, list) or len(selected_classifications) == 0:
        raise ValueError("selected_classifications must be a non-empty list for Call 2")

    # Validate classification names
    valid_names = list(CLASSIFICATIONS.values())
    invalid_classifications = [c for c in selected_classifications if c not in valid_names]
    if invalid_classifications:
        raise ValueError(f"Invalid classifications: {invalid_classifications}. Must match exact names from the list.")

    token = generate_token("classifications", {
        "background": background,
        "strategy": strategy,
        "selected_universities": selected_universities,
        "selected_classifications": selected_classifications,
        "classification_count": len(selected_classifications)
    })

    return {
        "classifications_token": token,
        "selected_classifications": selected_classifications,
        "classification_count": len(selected_classifications),
        "instructions": f"""
Classification selection complete.

SELECTION RESULTS:
- Selected classifications: {len(selected_classifications)}
- Classifications: {', '.join(selected_classifications[:5])}{"..." if len(selected_classifications) > 5 else ""}

NEXT STEP: Process university programs

Call process_university_programs(classifications_token) to begin university-by-university program filtering and selection.
        """,
        "next_step": "Call process_university_programs(classifications_token)"
    }


@mcp.tool
async def process_university_programs(
    classifications_token: str,
    university_programs: Optional[Dict[str, List[int]]] = None
) -> dict:
    """
    Filter and shortlist programs university-by-university.

    Iterative multi-call workflow processing one university per call to avoid context truncation.

    Args:
        classifications_token: From select_classifications()
        university_programs: Dict mapping university name to selected program IDs (None for first call)

    Returns:
        Current university programs + remaining_universities + instructions OR final programs_token
    """
    # API key validation
    tier, allowed_tools = validate_api_key_and_tool("process_university_programs")

    # ═══════════════════════════════════════════════════════════════
    # TYPE COERCION: Handle MCP serialization issues
    # ═══════════════════════════════════════════════════════════════
    import json
    if isinstance(university_programs, str):
        if university_programs == "" or university_programs.lower() == "null":
            university_programs = None
        else:
            try:
                university_programs = json.loads(university_programs)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid university_programs format: {university_programs}")
    # ═══════════════════════════════════════════════════════════════

    # Validate token
    classifications_data = validate_token(classifications_token, "classifications")
    background = classifications_data.get("background", "")
    strategy = classifications_data.get("strategy", "conservative")
    selected_universities = classifications_data.get("selected_universities", [])
    selected_classifications = classifications_data.get("selected_classifications", [])

    if not selected_universities:
        raise ValueError("No universities found in token.")

    if not selected_classifications:
        raise ValueError("No classifications found in token.")

    # Track processed universities
    if university_programs is None:
        university_programs = {}

    processed_universities = list(university_programs.keys())
    remaining_universities = [uni for uni in selected_universities if uni not in processed_universities]

    # If all universities processed, generate final token
    if not remaining_universities:
        # Calculate total programs
        total_programs = sum(len(programs) for programs in university_programs.values())

        token = generate_token("programs", {
            "background": background,
            "strategy": strategy,
            "universities": selected_universities,
            "university_programs": university_programs,
            "total_programs": total_programs,
            "selected_classifications": selected_classifications
        })

        return {
            "programs_token": token,
            "total_programs": total_programs,
            "universities_processed": len(university_programs),
            "instructions": f"""
ALL UNIVERSITIES PROCESSED

RESULTS:
- Universities: {len(university_programs)}
- Total programs selected: {total_programs}

NEXT STEP: Analyze and shortlist programs

Call analyze_and_shortlist(programs_token, university_analyses) to begin university-by-university analysis and shortlisting.
            """,
            "next_step": "Call analyze_and_shortlist(programs_token, university_analyses)"
        }

    # Process next university
    current_university = remaining_universities[0]

    # Get filtered programs for current university
    programs = _search_programs(current_university, classification_filters=selected_classifications)

    if not programs:
        # Skip universities with no matching programs
        return {
            "current_university": current_university,
            "programs": [],
            "program_count": 0,
            "remaining_universities": remaining_universities[1:],
            "remaining_count": len(remaining_universities) - 1,
            "instructions": f"""
{current_university}: NO PROGRAMS MATCH

No programs found matching selected classifications.

NEXT STEP: Continue to next university

Call process_university_programs(classifications_token, university_programs) again with:
- university_programs = {university_programs | {current_university: []}}

WARNING: DO NOT SKIP AHEAD. Process remaining {len(remaining_universities) - 1} universities before proceeding.
            """
        }

    # Format programs for display
    programs_display = "\n".join([f"  • [{p['id']}] {p['name']} ({p['degree']})" for p in programs])

    return {
        "current_university": current_university,
        "programs": programs,
        "program_count": len(programs),
        "remaining_universities": remaining_universities[1:],
        "remaining_count": len(remaining_universities) - 1,
        "instructions": f"""
{current_university} - {len(programs)} PROGRAMS FOUND

{programs_display}

YOUR TASK: Review program names and select relevant ones for this university
- Remove misleading programs even if classification matches
- Select programs matching student's profile and goals
- Include borderline cases (will be validated in next step)

NEXT STEP: Submit selection for {current_university}

Call process_university_programs(classifications_token, university_programs) again with:
- university_programs = {{"{current_university}": <list of selected program IDs>}} | {university_programs}

WARNING: DO NOT SKIP AHEAD. Process remaining {len(remaining_universities) - 1} universities before proceeding.
        """
    }


@mcp.tool
async def analyze_and_shortlist(
    programs_token: str,
    university_analyses: Optional[Dict[str, dict]] = None
) -> dict:
    """
    Analyze programs and shortlist per university with student profile research.

    Iterative multi-call workflow processing one university per call.

    IMPORTANT: Only send analysis for the CURRENT university in each call.
    The server automatically merges with previous analyses.

    Args:
        programs_token: From process_university_programs() or previous analyze_and_shortlist()
        university_analyses: Dict with ONLY current university's analysis (not all previous ones)
                           Format: {"University Name": {"shortlisted_programs": [...], "program_notes": {...}}}

    Returns:
        Current university analysis + remaining_universities + instructions OR final analysis_token

    Example workflow:
        Call 1: analyze_and_shortlist(token, {"Stanford": {...}})
        Call 2: analyze_and_shortlist(token_from_call1, {"Berkeley": {...}})
        Call N: analyze_and_shortlist(token_from_callN-1, {"Last Uni": {...}})
    """
    # API key validation
    tier, allowed_tools = validate_api_key_and_tool("analyze_and_shortlist")

    # ═══════════════════════════════════════════════════════════════
    # TYPE COERCION: Handle MCP serialization issues
    # ═══════════════════════════════════════════════════════════════
    import json
    if isinstance(university_analyses, str):
        if university_analyses == "" or university_analyses.lower() == "null":
            university_analyses = None
        else:
            try:
                university_analyses = json.loads(university_analyses)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid university_analyses format: {university_analyses}")
    # ═══════════════════════════════════════════════════════════════

    # Validate token (accepts both "programs" and "accumulation" types)
    token_data = _active_tokens.get(programs_token)
    if not token_data:
        raise ValueError("Invalid or expired token")

    token_type = token_data.get("type")
    if token_type == "programs":
        # First call: extract from programs token
        programs_data = validate_token(programs_token, "programs")
        accumulated_analyses = {}  # No history yet
    elif token_type == "accumulation":
        # Subsequent calls: extract from accumulation token
        programs_data = validate_token(programs_token, "accumulation")
        accumulated_analyses = programs_data.get("accumulated_analyses", {})
    else:
        raise ValueError(f"Invalid token type: {token_type}. Expected 'programs' or 'accumulation'")

    background = programs_data.get("background", "")
    strategy = programs_data.get("strategy", "conservative")
    universities = programs_data.get("universities", [])
    university_programs = programs_data.get("university_programs", {})

    if not universities:
        raise ValueError("No universities found in token.")

    # MERGE: Combine accumulated history with new submission (only current university)
    if university_analyses:
        # Validate: should only contain 1 university
        if len(university_analyses) > 1:
            raise ValueError(
                f"Submit only ONE university per call. You submitted {len(university_analyses)} universities: {list(university_analyses.keys())}\n"
                f"The server will merge analyses automatically."
            )
        accumulated_analyses.update(university_analyses)

    processed_universities = list(accumulated_analyses.keys())
    remaining_universities = [uni for uni in universities if uni not in processed_universities]

    # If all universities processed, generate final token
    if not remaining_universities:
        # Calculate total programs
        total_programs = sum(len(analysis.get("shortlisted_programs", [])) for analysis in accumulated_analyses.values())

        token = generate_token("analysis", {
            "background": background,
            "strategy": strategy,
            "universities": universities,
            "university_analyses": accumulated_analyses,
            "total_programs": total_programs
        })

        return {
            "analysis_token": token,
            "total_programs_shortlisted": total_programs,
            "universities_analyzed": len(accumulated_analyses),
            "instructions": f"""
ALL UNIVERSITIES ANALYZED

RESULTS:
- Universities: {len(accumulated_analyses)}
- Total programs shortlisted: {total_programs}

NEXT STEP: Select final programs

Call select_final_programs(analysis_token, final_programs) to choose final programs based on {strategy} strategy.
            """,
            "next_step": "Call select_final_programs(analysis_token, final_programs)"
        }

    # Generate accumulation token for next call
    accumulation_token = generate_token("accumulation", {
        "background": background,
        "strategy": strategy,
        "universities": universities,
        "university_programs": university_programs,
        "accumulated_analyses": accumulated_analyses
    })

    # Process next university
    current_university = remaining_universities[0]
    current_programs = university_programs.get(current_university, [])

    if not current_programs:
        # Skip universities with no programs
        return {
            "accumulation_token": accumulation_token,
            "current_university": current_university,
            "program_count": 0,
            "processed_count": len(accumulated_analyses),
            "remaining_universities": remaining_universities[1:],
            "remaining_count": len(remaining_universities) - 1,
            "instructions": f"""
{current_university}: NO PROGRAMS

This university has no programs to analyze.

NEXT STEP: Continue to next university

Call analyze_and_shortlist(accumulation_token, university_analyses) again with:
- accumulation_token = "{accumulation_token}"
- university_analyses = {{"{current_university}": {{"shortlisted_programs": [], "program_notes": {{}}}}}}

WARNING: DO NOT SKIP AHEAD. Process remaining {len(remaining_universities) - 1} universities before proceeding.
            """
        }

    # Get program details
    program_details = _get_program_details_batch(current_programs)
    programs_display = "\n".join([
        f"  • [{p['program_id']}] {p['program_name']} ({p['degree_type']})"
        for p in program_details
    ])

    return {
        "accumulation_token": accumulation_token,
        "current_university": current_university,
        "programs": program_details,
        "program_count": len(program_details),
        "processed_count": len(accumulated_analyses),
        "remaining_universities": remaining_universities[1:],
        "remaining_count": len(remaining_universities) - 1,
        "instructions": f"""
{current_university} - {len(program_details)} PROGRAMS

{programs_display}

YOUR TASK: Research and shortlist programs for this university

1. RESEARCH (optional, 0-3 web searches if uncertain about fit):
   - Research typical student profiles or career outcomes if needed
   - Keep findings brief (for internal decision-making only)

2. SHORTLIST: Select programs matching student's profile

3. WRITE NOTES: For each shortlisted program, write 20-40 word note explaining fit
   - Format: {{"program_id": {{"note": "Typical cohort: ..., Career outcomes: ..."}}}}
   - Focus on why this program fits THIS student's background/goals

NEXT STEP: Submit analysis for {current_university}

Call analyze_and_shortlist(accumulation_token, university_analyses) with:
- accumulation_token = "{accumulation_token}"
- university_analyses = {{"{current_university}": {{
    "shortlisted_programs": [list of selected program IDs],
    "program_notes": {{"program_id": {{"note": "20-40 words why this program fits"}}}},
    "optional_web_searches": [optional: 0-3 searches if needed]
  }}}}

IMPORTANT: Only send data for {current_university}, not previous universities.

Progress: {len(accumulated_analyses)} done, {len(remaining_universities)} remaining
        """
    }


@mcp.tool
async def upgrade_to_advanced(
    consultation_state_id: str
) -> dict:
    """
    Upgrade from basic tier to advanced tier

    Loads saved workflow state from PostgreSQL and resumes execution
    from analyze_programs_by_university() → generate_final_report_advanced() with Exa research

    Args:
        consultation_state_id: State ID from basic tier (format: cs_xxxxx)

    Returns:
        Validation token to continue workflow with analyze_programs_by_university()
    """
    # ═══════════════════════════════════════════════════════════════
    # API KEY & TOOL PERMISSION VALIDATION
    # ═══════════════════════════════════════════════════════════════
    tier_from_key, allowed_tools = validate_api_key_and_tool("upgrade_to_advanced")
    # ═══════════════════════════════════════════════════════════════

    import psycopg2
    import json
    from datetime import datetime

    # Load consultation state from PostgreSQL
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            dbname=os.getenv("POSTGRES_DB", "offeri"),
            user=os.getenv("POSTGRES_USER", "offeri_user"),
            password=os.getenv("POSTGRES_PASSWORD", "")
        )
        cursor = conn.cursor()

        # Fetch consultation state
        cursor.execute("""
            SELECT user_id, tier, workflow_step, workflow_data, created_at, expires_at
            FROM consultation_states
            WHERE id = %s
        """, (consultation_state_id,))

        result = cursor.fetchone()
        if not result:
            conn.close()
            raise ValueError(
                f"Consultation state not found: {consultation_state_id}\n\n"
                f"This state ID may be invalid, expired, or already used.\n"
                f"Please start a new basic consultation."
            )

        user_id, tier, workflow_step, workflow_data_json, created_at, expires_at = result

        # Check if expired
        if expires_at < datetime.utcnow():
            conn.close()
            raise ValueError(
                f"Consultation state expired: {consultation_state_id}\n\n"
                f"Created: {created_at}\n"
                f"Expired: {expires_at}\n\n"
                f"Consultation states are valid for 7 days. Please start a new basic consultation."
            )

        # Verify tier is basic
        if tier != 'basic':
            conn.close()
            raise ValueError(
                f"Invalid upgrade request: {consultation_state_id}\n\n"
                f"This consultation state is for tier '{tier}', not 'basic'.\n"
                f"Only basic tier consultations can be upgraded to advanced."
            )

        # Verify workflow step
        if workflow_step != 'validation_complete':
            conn.close()
            raise ValueError(
                f"Invalid workflow state: {consultation_state_id}\n\n"
                f"Current workflow step: {workflow_step}\n"
                f"Expected: validation_complete\n\n"
                f"This consultation is not ready for upgrade."
            )

        # Parse workflow data
        workflow_data = json.loads(workflow_data_json)
        validation_token = workflow_data.get("validation_token")
        total_programs = workflow_data.get("total_programs")
        universities = workflow_data.get("universities", [])

        if not validation_token:
            conn.close()
            raise ValueError(
                f"Invalid consultation state: {consultation_state_id}\n\n"
                f"Missing validation_token in workflow_data.\n"
                f"This state may be corrupted. Please start a new basic consultation."
            )

        # Update consultation state to 'advanced' tier
        cursor.execute("""
            UPDATE consultation_states
            SET tier = 'advanced', workflow_step = 'upgrade_initiated'
            WHERE id = %s
        """, (consultation_state_id,))

        conn.commit()
        conn.close()

        logger.info(f"UPGRADE: {consultation_state_id} upgraded from basic to advanced for user {user_id}")

        return {
            "upgraded": True,
            "consultation_state_id": consultation_state_id,
            "validation_token": validation_token,
            "total_programs": total_programs,
            "universities": len(universities),
            "message": f"""
Successfully upgraded to Advanced tier!

Consultation Details:
   • State ID: {consultation_state_id}
   • Programs validated: {total_programs}
   • Universities: {len(universities)}
   • Created: {created_at}

Next Step:
   Call analyze_programs_by_university(validation_token, university_analyses) to continue the workflow.

   Process each university with 2-round screening and collect structured analysis
   (career outcomes + target student profile) for your {total_programs} validated programs.
            """,
            "next_step": f"Call analyze_programs_by_university('{validation_token}', university_analyses)"
        }

    except psycopg2.Error as e:
        logger.error(f"PostgreSQL error in upgrade_to_advanced: {e}")
        raise ValueError(
            f"Database error while loading consultation state.\n\n"
            f"Error: {str(e)}\n\n"
            f"Please contact support at lyrica2333@gmail.com"
        )
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in upgrade_to_advanced: {e}")
        raise ValueError(
            f"Corrupted consultation state: {consultation_state_id}\n\n"
            f"Unable to parse workflow data. Please start a new basic consultation."
        )
    except Exception as e:
        logger.error(f"Unexpected error in upgrade_to_advanced: {e}")
        raise ValueError(
            f"Unexpected error while upgrading consultation.\n\n"
            f"Error: {str(e)}\n\n"
            f"Please contact support at lyrica2333@gmail.com"
        )


@mcp.tool
async def select_final_programs(
    analysis_token: str,
    final_programs: List[int]
) -> dict:
    """
    Select final programs for report based on strategy ratio.

    Args:
        analysis_token: From analyze_and_shortlist()
        final_programs: List of program IDs (10-30 programs)

    Returns:
        selection_token + statistics + next_step
    """
    # API key validation
    tier, allowed_tools = validate_api_key_and_tool("select_final_programs")

    # ═══════════════════════════════════════════════════════════════
    # TYPE COERCION: Handle MCP serialization issues
    # ═══════════════════════════════════════════════════════════════
    import json
    if isinstance(final_programs, str):
        try:
            final_programs = json.loads(final_programs)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid final_programs format: {final_programs}")
    # ═══════════════════════════════════════════════════════════════

    # Validate token
    analysis_data = validate_token(analysis_token, "analysis")
    background = analysis_data.get("background", "")
    strategy = analysis_data.get("strategy", "conservative")
    university_analyses = analysis_data.get("university_analyses", {})
    total_available = analysis_data.get("total_programs", 0)
    universities = analysis_data.get("universities", [])

    # Dynamic minimum programs based on university count
    university_count = len(universities)
    if university_count <= 7:
        min_programs = 10
        range_guidance = "at least 10 programs (fewer universities, focused selection)"
    else:
        min_programs = 20
        range_guidance = "at least 20 programs (more universities, broader coverage)"

    # Strategy ratios for guidance
    strategy_ratios = {
        "conservative": {"lottery": "10%", "reach": "30%", "target": "40%", "safety": "20%"},
        "aggressive": {"lottery": "20%", "reach": "50%", "target": "20%", "safety": "10%"}
    }
    ratios = strategy_ratios[strategy]

    # Validate final_programs
    if not final_programs or not isinstance(final_programs, list):
        raise ValueError("final_programs must be a non-empty list")

    program_count = len(final_programs)

    # Validate minimum only (no upper limit)
    if program_count < min_programs:
        raise ValueError(
            f"Too few programs: {program_count} programs.\n"
            f"With {university_count} universities, select at least {min_programs} programs from {total_available} analyzed programs.\n"
            f"Recommended: {range_guidance}"
        )

    # Generate selection token
    token = generate_token("selection", {
        "background": background,
        "strategy": strategy,
        "final_programs": final_programs,
        "program_count": program_count,
        "university_analyses": university_analyses
    })

    return {
        "selection_token": token,
        "program_count": program_count,
        "strategy": strategy,
        "university_count": university_count,
        "program_range": range_guidance,
        "instructions": f"""
FINAL PROGRAMS SELECTED

RESULTS:
- Universities: {university_count}
- Programs selected: {program_count}
- Recommended range: {range_guidance}
- Strategy: {strategy.capitalize()}
- Recommended distribution:
  - Lottery: {ratios['lottery']}
  - Reach: {ratios['reach']}
  - Target: {ratios['target']}
  - Safety: {ratios['safety']}

NEXT STEP: Generate final report

ALL TIERS: First call generate_final_report(selection_token, program_analyses)

The function will return:
- Basic tier: Report markdown (consultation complete)
- Advanced tier: Report markdown + can_generate_advanced=true
  → Then call generate_final_report_advanced(selection_token, program_research)
- Upgrade tier: Report markdown + consultation_state_id
  → Then call upgrade_to_advanced(consultation_state_id) first
  → Then call generate_final_report_advanced(selection_token, program_research)
        """,
        "next_step": "Call generate_final_report(selection_token, program_analyses) [ALL TIERS]"
    }


@mcp.tool
async def generate_final_report(
    selection_token: str,
    program_analyses: List[dict]
) -> dict:
    """
    Generate Basic tier report using LLM knowledge.

    ALL TIERS (basic/advanced/upgrade) must call this first.

    Args:
        selection_token: From select_final_programs()
        program_analyses: List of program analyses
            Each: {"program_id": int, "analysis": {"program_features": str, "student_experience": str, "suitability_analysis": str}}

    Returns:
        - report_markdown: The generated report
        - key_type: "basic" / "advanced" / "upgrade"
        - can_generate_advanced: Whether this key can call generate_final_report_advanced
        - consultation_state_id: State ID for upgrade tier (if key_type == "upgrade")
    """
    # API key validation
    tier, allowed_tools = validate_api_key_and_tool("generate_final_report")

    # ═══════════════════════════════════════════════════════════════
    # TYPE COERCION: Handle MCP serialization issues
    # ═══════════════════════════════════════════════════════════════
    import json
    if isinstance(program_analyses, str):
        try:
            program_analyses = json.loads(program_analyses)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid program_analyses format: {program_analyses}")
    # ═══════════════════════════════════════════════════════════════

    # Extract data from selection token
    selection_data = validate_token(selection_token, "selection")
    background = selection_data.get("background", "")
    strategy = selection_data.get("strategy", "conservative")
    final_programs = selection_data.get("final_programs", [])
    program_count = selection_data.get("program_count", 0)
    university_analyses = selection_data.get("university_analyses", {})

    # Validate program_analyses structure
    if not program_analyses or not isinstance(program_analyses, list):
        raise ValueError("program_analyses must be a non-empty list")

    # Validate each analysis has required fields
    for i, analysis in enumerate(program_analyses):
        if "program_id" not in analysis or "analysis" not in analysis:
            raise ValueError(f"program_analyses[{i}] missing 'program_id' or 'analysis' field")

        analysis_content = analysis["analysis"]
        required_fields = ["program_features", "student_experience", "suitability_analysis"]
        for field in required_fields:
            if field not in analysis_content:
                raise ValueError(f"program_analyses[{i}].analysis missing '{field}' field")
            if len(analysis_content[field]) < 100:
                raise ValueError(
                    f"program_analyses[{i}].analysis.{field} must be ≥100 characters. "
                    f"Current: {len(analysis_content[field])} characters"
                )

    # Generate basic report markdown (placeholder for now - LLM will generate)
    report_markdown = f"""# Study Abroad Consultation Report

## Basic Tier Report

Total Programs: {len(program_analyses)}

(Report content will be generated by LLM based on program_analyses)
"""

    # Determine tier-specific behavior
    can_generate_advanced = tier in ["advanced", "upgrade"]
    consultation_state_id = None

    # For "upgrade" tier, save consultation state to PostgreSQL
    if tier == "upgrade":
        import uuid
        import psycopg2

        consultation_state_id = f"cs_{uuid.uuid4().hex[:12]}"

        try:
            conn = get_pg_connection()
            cursor = conn.cursor()

            # Save consultation state
            cursor.execute("""
                INSERT INTO consultation_states
                (consultation_state_id, user_id, background, strategy, universities, final_programs, university_analyses, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                consultation_state_id,
                _current_user_id,
                background,
                strategy,
                json.dumps(list(university_analyses.keys())),
                json.dumps(final_programs),
                json.dumps(university_analyses)
            ))

            conn.commit()
            conn.close()

            logger.info(f"CONSULTATION STATE SAVED: {consultation_state_id} for user {_current_user_id}")

        except psycopg2.Error as e:
            logger.error(f"PostgreSQL error saving consultation state: {e}")
            raise ValueError(f"Failed to save consultation state: {str(e)}")

    # Return unified response
    result = {
        "report_generated": True,
        "report_markdown": report_markdown,
        "programs_analyzed": len(program_analyses),
        "key_type": tier,
        "can_generate_advanced": can_generate_advanced,
        "instructions": f"""
BASIC REPORT GENERATED

KEY INFO:
- Tier: {tier}
- Programs: {len(program_analyses)}
- Can generate advanced: {can_generate_advanced}
"""
    }

    # Add consultation_state_id for upgrade tier
    if tier == "upgrade":
        result["consultation_state_id"] = consultation_state_id
        result["instructions"] += f"""
UPGRADE TIER:
- Consultation state saved: {consultation_state_id}
- To generate advanced report:
  1. Call upgrade_to_advanced(consultation_state_id="{consultation_state_id}")
  2. Then call generate_final_report_advanced(selection_token, program_research)
"""
    elif tier == "advanced":
        result["instructions"] += """
ADVANCED TIER:
- You can now directly call generate_final_report_advanced(selection_token, program_research)
- Use 2 Exa searches per program (curriculum + career outcomes)
"""

    return result


@mcp.tool
async def generate_final_report_advanced(
    selection_token: str,
    program_research: List[dict]
) -> dict:
    """
    Generate Advanced tier report with Exa research.

    Args:
        selection_token: From select_final_programs()
        program_research: Program research with Exa searches and analyses

    Returns:
        Report completion message
    """
    # API key validation
    tier, allowed_tools = validate_api_key_and_tool("generate_final_report_advanced")

    # ═══════════════════════════════════════════════════════════════
    # TYPE COERCION: Handle MCP serialization issues
    # ═══════════════════════════════════════════════════════════════
    import json
    if isinstance(program_research, str):
        try:
            program_research = json.loads(program_research)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid program_research format: {program_research}")
    # ═══════════════════════════════════════════════════════════════

    # Extract data from selection token
    selection_data = validate_token(selection_token, "selection")

    return {
        "report_generated": True,
        "programs_analyzed": len(program_research),
        "message": """Report ready for generation.

INSTRUCTIONS:
- Programs to analyze: {} programs
- Each program: 200-400 words with Exa research findings
- Output in user's language
- DO NOT include tuition/timeline/costs
- Focus on program characteristics and student fit
        """.format(len(program_research))
    }


@mcp.tool
async def get_available_countries() -> str:
    """Get all countries with program counts. Use if unsure about country names."""
    # API key validation
    tier, allowed_tools = validate_api_key_and_tool("get_available_countries")

    countries = _get_available_countries()
    return "\n".join([f"{c['country']} ({c['count']} programs)" for c in countries])


@mcp.tool
async def get_database_statistics() -> dict:
    """Get database statistics for understanding data coverage."""
    # API key validation
    tier, allowed_tools = validate_api_key_and_tool("get_database_statistics")

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

        # Get user_id from API key (skip tracking for shared keys where user_id is NULL)
        cursor.execute("""
            SELECT user_id
            FROM api_keys
            WHERE id = %s AND is_active = true
        """, (api_key,))
        result = cursor.fetchone()

        if not result or not result[0]:  # Skip if no result or user_id is NULL (shared key)
            conn.close()
            return ""

        user_id = result[0]
        
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
