#!/usr/bin/env python3
"""
OfferI MCP Server - Simplified Version

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

    DATABASE ROLE: Search index for finding programs. Use web searches for conclusions.
    TOKEN BUDGET: Allocate 20% to DB queries, 80% to web searches.

    ═══════════════════════════════════════════════════════════════
    MANDATORY WORKFLOW
    ═══════════════════════════════════════════════════════════════

    Step 1: list_universities(country) - Get all universities

    Step 2: WEB SEARCH admission cases (CRITICAL - DO NOT SKIP!)
            Search: "GPA [X.X] [background] [country] [field] 录取案例 2024"
            Example: "GPA 3.3 双非 USA CS 录取案例 2024"
            Filter schools based on REAL admission outcomes

    Step 3: WEB SEARCH latest rankings (QS, Times, US News 2024-2025)
            Select 10-15 universities matching student profile

    Step 4: search_programs(university_name="X") for each selected school
            Returns plain text TSV - YOU filter by program names

    Step 5: get_program_details_optimized([id1, id2, ...]) for 50-200 programs
            Quick TSV format for initial screening

    Step 6: Filter to 30-50 programs, then get_program_details_batch([ids])
            Get complete details for scoring

    Step 7: Calculate scores for ALL programs:
            Score = Prestige(1-100) × Fit(1-100)
            Output TOP 30 programs ranked by score

    Step 8: WEB SEARCH TOP 10 programs (5-10 queries per program)
            Search for: location, workload, career outcomes, features, deadlines
            Query: "[University] [Program] 2025 admission career outcomes"

    Step 9: Generate comprehensive report with TOP 30 programs
            Include: Score, Prestige, Fit, 5 enhanced categories (地理/前景/压力/特色/时间线)

    ═══════════════════════════════════════════════════════════════
    TOOLS
    ═══════════════════════════════════════════════════════════════

    • list_universities(country) → Plain text: "Stanford\nMIT\n..."
    • search_programs(university_name) → TSV: "id\tname\n123\tCS M.Sc.\n..."
    • get_program_details_optimized([ids]) → 7-field TSV for bulk filtering
    • get_program_details_batch([ids]) → Full JSON details for final analysis
    • get_statistics() → Database overview
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
    Get COMPLETE details for ONE program. Returns all database fields.

    Use this after filtering programs from search results to get full information for analysis.

    Args:
        program_id: The program ID from search_programs() results

    Returns:
        Full program details including:
        - Basic info (program_name, university_name, country_standardized, city, degree_type)
        - Financial (tuition_min, tuition_max, currency)
        - Duration (duration_months, study_mode)
        - Content (description, program_structure)

    WORKFLOW:
        1. After filtering programs from search results
        2. Call this for each shortlisted program (typically 10-30 programs)
        3. Analyze complete details
        4. Generate final recommendations with scores
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM programs
        WHERE program_id = ?
    """, (program_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": f"Program {program_id} not found"}

    # Build dict with all fields
    program = {
        "program_id": row["program_id"],
        "program_name": row["program_name"],
        "university_name": row["university_name"],
        "country_standardized": row["country_standardized"],
        "city": row["city"],
        "degree_type": row["degree_type"],
        "study_mode": row["study_mode"],
        "duration_months": row["duration_months"],
        "tuition_min": row["tuition_min"],
        "tuition_max": row["tuition_max"],
        "currency": row["currency"],
        "description": row["description"],
        "program_structure": row["program_structure"]
    }

    # Remove null/empty fields to save tokens
    return clean_null_values(program)


@mcp.tool
async def get_program_details_batch(program_ids: List[int]) -> List[dict]:
    """
    Get COMPLETE details for MULTIPLE programs in ONE call.

    More efficient than calling get_program_details() 20+ times individually.
    Reduces token usage and API calls significantly.

    Args:
        program_ids: List of program IDs from search_programs() results

    Returns:
        List of full program details dictionaries (same format as get_program_details)

    WORKFLOW:
        1. After filtering programs from search results
        2. Call this ONCE with list of all shortlisted program IDs (typically 10-30)
        3. Analyze complete details for all programs
        4. Generate final recommendations with scores

    Example:
        # Old way: 20 individual calls
        # for pid in [123, 456, 789, ...]:
        #     details = get_program_details(pid)  # 20 calls!

        # New way: 1 batch call
        details = get_program_details_batch([123, 456, 789, ...])  # 1 call!
    """
    if not program_ids:
        return []

    conn = get_db_connection()
    cursor = conn.cursor()

    # Use SQL IN clause for batch query
    placeholders = ','.join('?' * len(program_ids))
    query = f"SELECT * FROM programs WHERE program_id IN ({placeholders})"

    cursor.execute(query, program_ids)
    results = cursor.fetchall()
    conn.close()

    # Build list of full details and clean nulls to save tokens
    programs = [{
        "program_id": row["program_id"],
        "program_name": row["program_name"],
        "university_name": row["university_name"],
        "country_standardized": row["country_standardized"],
        "city": row["city"],
        "degree_type": row["degree_type"],
        "study_mode": row["study_mode"],
        "duration_months": row["duration_months"],
        "tuition_min": row["tuition_min"],
        "tuition_max": row["tuition_max"],
        "currency": row["currency"],
        "description": row["description"],
        "program_structure": row["program_structure"]
    } for row in results]

    # Remove null/empty fields to save tokens
    return [clean_null_values(p) for p in programs]


@mcp.tool
async def get_program_details_optimized(program_ids: List[int]) -> str:
    """Get 7 key fields for bulk filtering (50-200 programs).
    Returns TSV: "id\tname\tuniversity\tcountry\tcost\tmonths\tdegree"
    Header on first line only.

    Use this for initial screening of many programs.
    Then call get_program_details_batch() for TOP 30 programs."""
    if not program_ids:
        return "id\tname\tuniversity\tcountry\tcost\tmonths\tdegree"

    conn = get_db_connection()
    cursor = conn.cursor()

    placeholders = ','.join('?' * len(program_ids))
    query = f"""
        SELECT program_id, program_name, university_name, country_standardized,
               tuition_max, duration_months, degree_type
        FROM programs
        WHERE program_id IN ({placeholders})
    """

    cursor.execute(query, program_ids)
    results = cursor.fetchall()
    conn.close()

    # TSV format with header-once
    lines = ["id\tname\tuniversity\tcountry\tcost\tmonths\tdegree"]
    for row in results:
        lines.append(
            f"{row['program_id']}\t"
            f"{row['program_name']}\t"
            f"{row['university_name']}\t"
            f"{row['country_standardized'] or 'N/A'}\t"
            f"{row['tuition_max'] or 'N/A'}\t"
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
