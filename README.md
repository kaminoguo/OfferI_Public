# OfferI MCP Server

> 🎓 Study Abroad Program Database for AI Assistants via MCP

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-blue.svg)](https://modelcontextprotocol.io)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## 📖 What is This?

**OfferI MCP Server** provides AI assistants (Claude, GPT, etc.) access to a comprehensive database of **89,986 Master's degree programs** worldwide through the [Model Context Protocol (MCP)](https://modelcontextprotocol.io).

### Key Features

- 🌍 **Global Coverage**: 89,986 Master's programs from universities worldwide
- 🔍 **Smart Search**: Search by country, university, budget, duration, degree type
- 📊 **Rich Data**: 13 structured fields including tuition, duration, requirements, descriptions
- ⚡ **Fast Queries**: Optimized SQLite database with batch operations
- 🔒 **Secure**: Database stays on server, users query via MCP protocol
- 🆓 **Free to Use**: Open source MIT license

### Supported AI Platforms

- ✅ Claude (Claude Desktop, Claude Code)
- ✅ GPT-4 (via MCP clients)
- ✅ Any LLM that supports MCP protocol

## 🚀 Quick Start

### For Claude Users

**Method 1: Auto-configuration (Recommended)**

```bash
# Add MCP server to Claude
claude mcp add --transport sse offeri https://mcp.offeri.io/sse

# Start using in Claude
"Find me affordable CS Master's programs in Europe"
```

**Method 2: Manual Configuration**

Edit your Claude config file (`~/.claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "offeri": {
      "type": "sse",
      "url": "https://mcp.offeri.io/sse"
    }
  }
}
```

### For Self-Hosted Setup

```bash
# 1. Clone repository
git clone https://github.com/kaminoguo/OfferI_MCP.git
cd OfferI_MCP

# 2. Install dependencies
pip install -r requirements.txt

# 3. Download database (53MB)
wget https://mcp.offeri.io/database/programs.db

# 4. Run MCP server
python server_http.py --transport sse --host 0.0.0.0 --port 8081
```

Then configure your MCP client to use `http://localhost:8081/sse`

## 📚 Available Tools

The MCP server provides 7 powerful tools:

### 1. `get_available_countries()`
Get list of all countries with program counts.

```
Example output:
USA (15,234 programs)
United Kingdom (12,456 programs)
Germany (8,789 programs)
...
```

### 2. `list_universities(country)`
List all universities in a specific country.

```python
# Example
list_universities("USA")

# Returns:
Stanford University
MIT
Harvard University
...
```

### 3. `search_programs(...)`
Search programs with flexible filters.

**Parameters:**
- `university_name` (optional): Filter by university
- `country` (optional): Filter by country
- `budget_max` (optional): Maximum tuition in USD
- `duration_max` (optional): Maximum duration in months
- `degree_type` (optional): Degree type (e.g., "M.Sc.", "MBA")

```python
# Example
search_programs(
    country="USA",
    budget_max=50000,
    duration_max=24
)

# Returns TSV format:
program_id    program_name
12345        Computer Science M.Sc.
67890        Data Science M.Sc.
...
```

### 4. `get_program_details(program_id)`
Get complete details for a single program.

```python
# Example
get_program_details(12345)

# Returns:
{
  "program_id": 12345,
  "program_name": "Computer Science M.Sc.",
  "university_name": "Stanford University",
  "country_standardized": "USA",
  "city": "Stanford, CA",
  "degree_type": "M.Sc.",
  "duration_months": 24,
  "tuition_min": 55000,
  "tuition_max": 58000,
  "currency": "USD",
  "description": "...",
  "program_structure": "...",
  ...
}
```

### 5. `get_program_details_batch(program_ids)`
Get details for multiple programs efficiently (recommended for 10-30 programs).

```python
# Example
get_program_details_batch([12345, 67890, 11111])

# Returns array of program details
[{...}, {...}, {...}]
```

### 6. `get_program_details_optimized(program_ids)`
Get 7 key fields for bulk screening (50-200 programs).

Returns TSV format with: `id`, `name`, `university`, `country`, `cost`, `months`, `degree`

### 7. `get_statistics()`
Get database statistics and overview.

```python
# Returns:
{
  "total_programs": 89986,
  "data_quality": {...},
  "top_countries": [...],
  "top_universities": [...],
  "degree_types": [...]
}
```

## 💡 Usage Examples

### Example 1: Find Affordable Programs

```
User: "I want to study CS in Europe, budget under $20,000"

AI (using MCP):
1. list_universities("Germany")  # Free tuition
2. search_programs(country="Germany", university_name="TU Munich")
3. get_program_details_batch([id1, id2, id3])
4. Analyze and recommend top 3 programs
```

### Example 2: Compare Universities

```
User: "Compare CS programs at MIT, Stanford, and CMU"

AI (using MCP):
1. search_programs(university_name="MIT")
2. search_programs(university_name="Stanford")
3. search_programs(university_name="Carnegie Mellon")
4. get_program_details_batch([ids])
5. Create comparison table
```

### Example 3: Career-Focused Search

```
User: "Best programs for AI/ML career, willing to relocate anywhere"

AI (using MCP):
1. get_available_countries()
2. search_programs() for top AI universities
3. Web search for latest AI rankings
4. get_program_details_batch([top_program_ids])
5. Rank by: reputation, cost, career outcomes
```

## 📊 Database Schema

### Program Fields (13 total)

| Field | Type | Description | Coverage |
|-------|------|-------------|----------|
| `program_id` | int | Unique identifier | 100% |
| `program_name` | string | Program name | 100% |
| `university_name` | string | University name | 100% |
| `country_standardized` | string | Country (ISO format) | 100% |
| `city` | string | City location | 95% |
| `degree_type` | string | Degree type (M.Sc., MBA, etc.) | 98% |
| `duration_months` | int | Program duration | 87% |
| `tuition_min` | float | Minimum tuition | 65% |
| `tuition_max` | float | Maximum tuition | 65% |
| `currency` | string | Currency code | 65% |
| `description` | string | Program description | 92% |
| `program_structure` | string | Curriculum details | 78% |
| `study_mode` | string | Full-time/Part-time | 85% |

### Database Stats

- **Total Programs**: 89,986 Master's programs
- **Database Size**: 53MB (optimized SQLite)
- **Update Frequency**: Quarterly
- **Data Source**: Public university websites and education portals

## 🔧 Advanced Configuration

### Rate Limiting (for self-hosted)

If hosting publicly, add rate limiting:

```python
# In server_http.py
from rate_limiter import check_rate_limit

@mcp.tool
async def search_programs(...):
    api_key = request.headers.get("X-API-Key")
    if not check_rate_limit(api_key, limit=100):  # 100 requests/day
        raise Exception("Rate limit exceeded")
    # ... rest of function
```

### Custom Deployment

Deploy on your own infrastructure:

```bash
# Docker deployment
docker build -t offeri-mcp .
docker run -p 8081:8081 \
    -v $(pwd)/programs.db:/app/programs.db \
    offeri-mcp

# Or use docker-compose
docker-compose up -d
```

### API Authentication

For production deployments, add API key authentication:

```json
{
  "mcpServers": {
    "offeri": {
      "type": "sse",
      "url": "https://your-server.com/sse",
      "headers": {
        "X-API-Key": "your_api_key_here"
      }
    }
  }
}
```

## 🏗️ Architecture

```
┌─────────────────┐
│   AI Assistant  │ (Claude, GPT, etc.)
└────────┬────────┘
         │ MCP Protocol
┌────────▼────────┐
│   MCP Server    │ (FastMCP + HTTP/SSE)
└────────┬────────┘
         │ SQL Queries
┌────────▼────────┐
│ SQLite Database │ (89,986 programs, 53MB)
└─────────────────┘
```

## 📖 Recommended Workflow

The MCP server is designed to work with AI assistants following this workflow:

1. **Country Selection**: `list_universities(country)` or `get_available_countries()`
2. **Web Search**: AI searches latest university rankings (QS, Times, US News)
3. **Program Search**: `search_programs()` for selected universities
4. **Filter**: AI filters programs by name/field
5. **Bulk Screening**: `get_program_details_optimized([50-200 ids])` for initial filtering
6. **Detailed Analysis**: `get_program_details_batch([10-30 ids])` for top candidates
7. **Final Recommendations**: AI ranks programs based on user profile

This workflow minimizes token usage while maximizing result quality.

## 🛠️ Development

### Requirements

- Python 3.11+
- FastMCP 0.2.0+
- SQLite 3.8+

### Installation

```bash
# Clone repository
git clone https://github.com/kaminoguo/OfferI_MCP.git
cd OfferI_MCP

# Install dependencies
pip install -r requirements.txt

# Run tests (if available)
pytest tests/

# Start development server
python server_http.py --transport sse --port 8081
```

### Project Structure

```
OfferI_MCP/
├── server_http.py          # MCP server implementation
├── requirements.txt        # Python dependencies
├── programs.db            # Database (download separately)
├── README.md             # This file
├── LICENSE              # MIT License
└── examples/
    └── usage_examples.md  # More examples
```

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## 📜 License

**MIT License** - See [LICENSE](LICENSE) for details.

### Data Usage

- Data sourced from public university websites and education portals
- For educational and personal use only
- Commercial use: Please contact for licensing

## 🌟 Use Cases

- **Students**: Find programs matching your profile
- **Consultants**: Quick program lookup for clients
- **Researchers**: Analyze study abroad trends
- **Developers**: Build education-focused AI apps
- **Universities**: Benchmark programs

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/kaminoguo/OfferI_MCP/issues)
- **Documentation**: [Full Docs](https://docs.offeri.io)
- **Email**: support@offeri.io

## 🙏 Credits

- Built with [FastMCP](https://github.com/jlowin/fastmcp)
- Powered by [Model Context Protocol](https://modelcontextprotocol.io)
- Data from public education resources

## ⚠️ Disclaimer

This tool provides information for reference purposes only. Always verify program details with official university websites before making decisions.

---

**Built with ❤️ for international students worldwide**

Made by [@kaminoguo](https://github.com/kaminoguo)
