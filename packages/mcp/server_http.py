#!/usr/bin/env python3
"""
OfferI MCP Server - HTTP/SSE Version (Public)

Synced from backend/mcp/server.py with flexible transport modes

Philosophy: Be DUMB, return RAW data, let LLM be SMART.

No complicated matching logic. No "intelligent" filtering.
Just query the database and return results. The LLM will decide what's relevant.
"""
import os
import sqlite3
from pathlib import Path
from typing import Optional, List, Any, Dict, Union
from fastmcp import FastMCP

# Database path
DB_PATH = os.getenv("DB_PATH", str(Path(__file__).parent / "programs.db"))

# Initialize FastMCP server
mcp = FastMCP(
    name="OfferI Study Abroad",
    instructions="""
    Study abroad program database with 93,716 programs worldwide.
    Current date: October 2025

    DATABASE ROLE: Search index for finding programs. Use web searches for conclusions.
    TOKEN BUDGET: Allocate 15% to DB queries, 85% to web searches.

    LANGUAGE POLICY: Output language MUST match user's input language.
    - If user writes in English → respond in English
    - If user writes in Chinese → respond in Chinese

    ═══════════════════════════════════════════════════════════════
    MANDATORY WORKFLOW
    ═══════════════════════════════════════════════════════════════

    Step 1: list_universities(country) - Get all universities

    Step 2: WEB SEARCH admission cases (CRITICAL - DO 3-5 SEARCHES!)
            Multiple searches with different keywords to find REAL outcomes:
            - "GPA [X.X] [internship] [field] graduate admission 2024 2025"
            - "low GPA strong experience graduate school acceptance [country]"
            - "[Background] [field] masters admission outcomes 2024"
            Filter schools based on real admission outcomes, NOT guesses

    Step 3: WEB SEARCH latest rankings (DO 2-3 SEARCHES)
            Search for 2024-2025 rankings:
            - "QS World University Rankings 2025 [field]"
            - "US News Best Graduate [field] Programs 2025"
            - "Times Higher Education 2024 2025 [field] rankings"
            Select 15-20 universities matching student profile

    Step 4: search_programs(university_name="X") for each selected school
            Returns plain text TSV - YOU filter by program names

    Step 5: get_program_details_optimized([id1, id2, ...]) for 100-200 programs
            Quick TSV format for initial screening (minimal fields)

    Step 6: Filter to 30-50 programs, then get_program_details_batch([ids])
            Get essential details for scoring (NO tuition data - unreliable)

    Step 7: Calculate transparent scores for ALL programs:
            Score = Prestige(1-100) × Fit(1-100)
            Show breakdown:
            - Prestige: ranking(40%) + reputation(30%) + outcomes(30%)
            - Fit: career_alignment(40%) + technical_depth(20%) + location(20%) + other(20%)

    Step 8: WEB SEARCH TOP 10 programs (DO 6-10 QUERIES PER PROGRAM!)
            For EACH of top 10 programs, search multiple angles:
            - "[University] [Program] career outcomes salary 2024 2025"
            - "[University] [Program] admission requirements deadline 2025 2026"
            - "[University] [Program] student review reddit experience"
            - "[University] [Program] alumni LinkedIn placement companies"
            - "[University] [Program] vs [competitor] comparison"
            - "[University] [Program] location housing cost living"
            - "[University] [Program] workload difficulty pressure"
            - "[University] [Program] tuition fees cost 2025 2026"
            THIS IS CRITICAL - Expect 60-100 total web searches for top 10!

    Step 9: Generate comprehensive report with TOP 30 programs
            Output in user's language. Include for each program:
            - Location & Environment
            - Career Prospects & Real Outcomes
            - Program Intensity & Workload
            - Unique Features & Differentiation
            - Application Timeline & Requirements
            - Tuition (from web search, NOT database)

    ═══════════════════════════════════════════════════════════════
    TOOLS
    ═══════════════════════════════════════════════════════════════

    • list_universities(country) → Plain text list
    • search_programs(university_name) → TSV: "id\tname"
    • get_program_details_optimized([ids]) → Minimal TSV for filtering
    • get_program_details_batch([ids]) → Essential fields ONLY (no tuition/description/structure)
    • get_statistics() → Database overview

    CRITICAL: Database tuition data is UNRELIABLE. Always get tuition from web search.
    """
)


def get_db_connection():
    """Create database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def clean_null_values(data: Any) -> Any:
    """
    Recursively remove null/empty values from data to save tokens.
    Removes: None, empty strings, 'N/A', 'null', empty lists, empty dicts
    """
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


@mcp.tool
async def get_available_countries() -> str:
    """
    Get a list of ALL countries in the database with program counts.
    Use this FIRST if you're not sure about the exact country name.

    Returns:
        String: All countries with program counts, one per line
    """
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

    return "\n".join([f"{row['country_standardized']} ({row['count']} programs)" for row in results])


@mcp.tool
async def list_universities(country: str) -> str:
    """Get ALL universities in a country. If country not found, returns all available countries.

    Use get_available_countries() first to see exact country names like 'USA', 'Hong Kong (SAR)'."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Try exact match first (most accurate)
    cursor.execute("""
        SELECT university_name
        FROM programs
        WHERE country_standardized = ?
        GROUP BY university_name
        ORDER BY COUNT(*) DESC
    """, [country])
    results = cursor.fetchall()

    # If no match, return all available countries
    if not results:
        cursor.execute("""
            SELECT country_standardized, COUNT(*) as count
            FROM programs
            WHERE country_standardized IS NOT NULL
            GROUP BY country_standardized
            ORDER BY count DESC
        """)
        all_countries = cursor.fetchall()
        conn.close()

        countries_str = "\n".join([f"{row['country_standardized']} ({row['count']} programs)"
                                   for row in all_countries])
        return f"'{country}' not found. Available countries:\n\n{countries_str}\n\nUse exact name from above."

    conn.close()
    return "\n".join([row["university_name"] for row in results])


@mcp.tool
async def search_programs(
    university_name: Optional[str] = None,
    country: Optional[str] = None,
    budget_max: Optional[int] = None,
    duration_max: Optional[int] = None,
    degree_type: Optional[str] = None
) -> str:
    """Search programs. Returns TSV: "program_id\tprogram_name\n123\tCS M.Sc.\n..."

    Filter by program names yourself (be inclusive with variations).
    Then call get_program_details_batch() for shortlisted programs."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT program_id, program_name
        FROM programs
        WHERE 1=1
    """
    params = []

    if university_name:
        query += " AND LOWER(university_name) LIKE LOWER(?)"
        params.append(f"%{university_name}%")

    if country:
        query += " AND LOWER(country_standardized) LIKE LOWER(?)"
        params.append(f"%{country}%")

    if budget_max:
        query += " AND (tuition_max IS NULL OR tuition_max <= ?)"
        params.append(budget_max)

    if duration_max:
        query += " AND (duration_months IS NULL OR duration_months <= ?)"
        params.append(duration_max)

    if degree_type:
        query += " AND degree_type = ?"
        params.append(degree_type)

    query += " ORDER BY program_name"

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    # TSV format with header-once
    lines = ["program_id\tprogram_name"]
    for row in results:
        lines.append(f"{row['program_id']}\t{row['program_name']}")
    return "\n".join(lines)


@mcp.tool
async def get_program_details(program_id: int) -> dict:
    """
    Get ESSENTIAL details for ONE program.

    OPTIMIZED: Returns only essential fields to save tokens.
    Use get_program_details_batch() for multiple programs (more efficient).

    Args:
        program_id: The program ID from search_programs() results

    Returns:
        Essential program details (NO tuition/description/structure)

    Fields returned:
        - program_id, program_name, university_name
        - country_standardized, city, degree_type
        - duration_months, is_part_time (if applicable)

    NOTE: Database tuition data is UNRELIABLE - get from web search.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT program_id, program_name, university_name,
               country_standardized, city, degree_type,
               duration_months, study_mode
        FROM programs
        WHERE program_id = ?
    """, (program_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": f"Program {program_id} not found"}

    # Build dict with essential fields only
    program = {
        "program_id": row["program_id"],
        "program_name": row["program_name"],
        "university_name": row["university_name"],
        "country_standardized": row["country_standardized"],
        "city": row["city"],
        "degree_type": row["degree_type"],
        "duration_months": row["duration_months"]
    }

    # Convert study_mode to boolean (saves tokens)
    study_mode = row["study_mode"]
    if study_mode and "part" in study_mode.lower():
        program["is_part_time"] = True

    # Remove null/empty fields to save tokens
    return clean_null_values(program)


@mcp.tool
async def get_program_details_batch(program_ids: List[int]) -> List[dict]:
    """
    Get ESSENTIAL details for MULTIPLE programs in ONE call.

    OPTIMIZED: Returns only essential fields to save tokens.
    Database tuition data is UNRELIABLE - get from web search instead.

    Args:
        program_ids: List of program IDs from search_programs() results

    Returns:
        List of essential program details (NO tuition/description/structure)

    Fields returned:
        - program_id, program_name, university_name
        - country_standardized, city, degree_type
        - duration_months, is_part_time

    WORKFLOW:
        1. After filtering from optimized search (100-200 programs)
        2. Call this ONCE with shortlisted IDs (30-50 programs)
        3. Analyze and score all programs
        4. Do extensive web searches for top 10

    Example:
        details = get_program_details_batch([123, 456, 789, ...])
    """
    if not program_ids:
        return []

    conn = get_db_connection()
    cursor = conn.cursor()

    # Use SQL IN clause for batch query - select only essential fields
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

    # Build list with essential fields only and convert study_mode to boolean
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

        # Convert study_mode to boolean (saves tokens)
        study_mode = row["study_mode"]
        if study_mode and "part" in study_mode.lower():
            program["is_part_time"] = True

        programs.append(program)

    # Remove null/empty fields to save tokens
    return [clean_null_values(p) for p in programs]


@mcp.tool
async def get_program_details_optimized(program_ids: List[int]) -> str:
    """Get 6 essential fields for bulk filtering (100-200 programs).
    Returns TSV: "id\tname\tuniversity\tcountry\tmonths\tdegree"
    Header on first line only.

    NO tuition (database data unreliable - get from web search).

    Use this for initial screening of many programs.
    Then call get_program_details_batch() for TOP 30-50 programs."""
    if not program_ids:
        return "id\tname\tuniversity\tcountry\tmonths\tdegree"

    conn = get_db_connection()
    cursor = conn.cursor()

    placeholders = ','.join('?' * len(program_ids))
    query = f"""
        SELECT program_id, program_name, university_name, country_standardized,
               duration_months, degree_type
        FROM programs
        WHERE program_id IN ({placeholders})
    """

    cursor.execute(query, program_ids)
    results = cursor.fetchall()
    conn.close()

    # TSV format with header-once (no tuition field)
    lines = ["id\tname\tuniversity\tcountry\tmonths\tdegree"]
    for row in results:
        lines.append(
            f"{row['program_id']}\t"
            f"{row['program_name']}\t"
            f"{row['university_name']}\t"
            f"{row['country_standardized'] or 'N/A'}\t"
            f"{row['duration_months'] or 'N/A'}\t"
            f"{row['degree_type'] or 'N/A'}"
        )
    return "\n".join(lines)


@mcp.tool
async def get_statistics() -> dict:
    """
    Database statistics. Useful for understanding what data is available.

    Returns:
        Overall stats, top countries, top universities, degree types
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Total programs
    cursor.execute("SELECT COUNT(*) as total FROM programs")
    total = cursor.fetchone()["total"]

    # Data quality stats
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN tuition_max IS NOT NULL THEN 1 ELSE 0 END) as with_tuition,
            SUM(CASE WHEN duration_months IS NOT NULL THEN 1 ELSE 0 END) as with_duration,
            SUM(CASE WHEN degree_type IS NOT NULL THEN 1 ELSE 0 END) as with_degree_type,
            SUM(CASE WHEN country_standardized IS NOT NULL THEN 1 ELSE 0 END) as with_country_std
        FROM programs
    """)
    quality = cursor.fetchone()

    # By country (standardized)
    cursor.execute("""
        SELECT country_standardized as country, COUNT(*) as count
        FROM programs
        WHERE country_standardized IS NOT NULL
        GROUP BY country_standardized
        ORDER BY count DESC
        LIMIT 15
    """)
    countries = [{"country": row["country"], "count": row["count"]} for row in cursor.fetchall()]

    # Top universities
    cursor.execute("""
        SELECT university_name, country_standardized as country, COUNT(*) as program_count
        FROM programs
        WHERE university_name IS NOT NULL
        GROUP BY university_name
        ORDER BY program_count DESC
        LIMIT 20
    """)
    universities = [{"university": row["university_name"], "country": row["country"], "programs": row["program_count"]} for row in cursor.fetchall()]

    # By degree type
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
        "data_quality": {
            "with_tuition": f"{quality['with_tuition']}/{total} ({quality['with_tuition']/total*100:.1f}%)",
            "with_duration": f"{quality['with_duration']}/{total} ({quality['with_duration']/total*100:.1f}%)",
            "with_degree_type": f"{quality['with_degree_type']}/{total} ({quality['with_degree_type']/total*100:.1f}%)",
            "with_country_std": f"{quality['with_country_std']}/{total} ({quality['with_country_std']/total*100:.1f}%)"
        },
        "top_countries": countries,
        "top_universities": universities,
        "degree_types": degrees
    }


if __name__ == "__main__":
    # Flexible transport mode (HTTP/SSE for public, STDIO for local)
    import argparse

    parser = argparse.ArgumentParser(description="OfferI MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="sse",
                       help="Transport mode: stdio (for local) or sse (for HTTP)")
    parser.add_argument("--host", default="0.0.0.0",
                       help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8081,
                       help="Port to listen on (default: 8081)")
    args = parser.parse_args()

    if args.transport == "sse":
        print(f"🚀 Starting OfferI MCP Server (HTTP/SSE mode)")
        print(f"📡 Server URL: http://{args.host}:{args.port}")
        print(f"💾 Database: {DB_PATH}")
        print(f"✨ Ready to serve!")
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        # STDIO mode for local use
        mcp.run()
