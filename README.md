<div align="center">

# OfferI

### AI-Powered Study Abroad Consultation Platform

*Personalized master's program recommendations using Claude Code and MCP*

[![Live Demo](https://img.shields.io/badge/Live_Demo-offeri.org-5B5BD6?style=flat-square)](https://offeri.org)
[![License](https://img.shields.io/badge/License-Elastic_2.0-blue.svg?style=flat-square)](LICENSE)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-764ba2?style=flat-square)](https://modelcontextprotocol.io)

[Live Demo](https://offeri.org) · [Documentation](./docs) · [Issues](https://github.com/kaminoguo/OfferI_Public/issues)

</div>

---

## Overview

**OfferI** is an AI-powered study abroad consultation platform that provides personalized master's program recommendations from a curated database of **100,000+ programs** worldwide.

Unlike traditional consultants charging $2,000-5,000, OfferI delivers professional analysis for **$6 per consultation**, with reports generated in **10-15 minutes**.

### Current Focus

**Master's Programs Only** (MVP Phase)

After validating product-market fit, we plan to expand to:
- Bachelor's programs
- PhD programs (including professor recommendations)
- Non-English taught programs

---

## Technical Architecture

### Core Technical Advantages

**1. MCP Direct Database Access → Lower Hallucination Rate**

Unlike RAG (Retrieval-Augmented Generation) which uses vector similarity matching, we use **MCP (Model Context Protocol) for direct SQL queries**:

- **RAG Approach**: Text → Embeddings → Vector Search → ~85% semantic accuracy (hallucination risk)
- **Our Approach**: MCP → Direct SQL Query → 100% deterministic results (zero hallucination)

For structured data like university programs (name, tuition, duration), SQL is inherently more reliable than semantic similarity.

**2. Using Official CLI → Product Improves Automatically**

We use **Claude Code CLI** (official tool from Anthropic):

- **Our Advantage**: When Anthropic updates Claude Code, our product gets better automatically
- **LangChain/LangGraph Risk**: Framework abstractions can break with LLM updates, requiring constant maintenance

Using vendor-official tools means we benefit from their improvements without additional engineering work.

---

## Tech Stack

**Frontend**
- Next.js 15 (App Router)
- React 19
- TypeScript
- Tailwind CSS
- Clerk (Authentication)
- Stripe (Payments)

**Backend**
- FastAPI (Python 3.11)
- Redis (Job queue)
- PostgreSQL (User data)
- Worker Pool (concurrent processing)

**AI/LLM**
- Claude Code CLI (Headless mode)
- MCP (Model Context Protocol)
- Two-stage pipeline (Analysis + Review)

**Infrastructure**
- Docker + Docker Compose
- DigitalOcean (Singapore)
- Nginx (Reverse proxy)
- WeasyPrint (PDF generation)

---

## Using Our MCP Server

Our MCP server is available for developers building AI applications with study abroad data.

### Quick Setup

**Step 1: Get API Key**
- Visit https://offeri.org/settings
- Create a free account and generate an API key
- Free tier: 5 MCP queries per month

**Step 2: Add to Claude Code CLI**

```bash
claude mcp add offeri --transport http https://api.offeri.org/mcp \
  -H "Authorization: Bearer sk_live_YOUR_API_KEY_HERE"
```

**Step 3: Add to Claude Desktop**

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "offeri": {
      "url": "https://api.offeri.org/mcp",
      "transport": "http",
      "headers": {
        "Authorization": "Bearer sk_live_YOUR_API_KEY_HERE"
      }
    }
  }
}
```

### Usage Example

```
You: Find computer science master's programs in Singapore
     for a student with 3.5 GPA and $50K budget

Claude: [Uses OfferI MCP to query 93,716 programs...]
        Found 12 matching programs in Singapore:
        1. NUS MSc Computer Science - $45K, 1.5 years
        2. NTU MSc AI - $42K, 1 year
        ...
```

## Roadmap

**Current (v1.0)**
- Master's programs worldwide
- AI recommendation engine
- Web application (Next.js + FastAPI)
- Payment integration
- PDF report generation

**Planned Expansion** (after validating product-market fit)
- Bachelor's programs
- PhD programs with professor recommendations
- Non-English taught programs (French, German, Spanish, etc.)
- Mobile application
- API access for developers

## License

**Elastic License 2.0** - Same license used by Elasticsearch and Kibana

**What You CAN Do:**
- ✅ Use the code for learning and education
- ✅ Modify and deploy for your own internal projects
- ✅ Study the implementation and architecture
- ✅ Contribute improvements via pull requests

**What You CANNOT Do:**
- ❌ Offer this software as a hosted/managed SaaS service to third parties
- ❌ Build a competing study abroad consultation platform using our code
- ❌ Sell access to the software's features or functionality

**Proprietary Components (Not in This Repository):**
- Database (100,000+ programs)
- Crawler implementation
- Data processing tools

**Why Elastic License 2.0?**

We chose this license to protect our commercial service while keeping code accessible for learning. It's the same approach used by companies like Elastic, ensuring our 6+ months of development work isn't immediately copied by competitors.

See [LICENSE](./LICENSE) for full legal text.

---

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](./docs/ARCHITECTURE.md) | System design deep-dive |
| [MCP Guide](./docs/MCP.md) | Model Context Protocol usage |
| [Deployment](./docs/DEPLOYMENT.md) | Production deployment guide |

---

## Contact

**Email**: lyrica2333@gmail.com

**GitHub Issues**: [Report bugs or request features](https://github.com/kaminoguo/OfferI_Public/issues)

**Website**: [offeri.org](https://offeri.org)

---

## Disclaimer

Information provided by OfferI is for reference purposes only and does not constitute professional study abroad consulting advice. Always verify information with official university websites before making application decisions.

---

<div align="center">

**Star this repository if you find it useful**

[![GitHub stars](https://img.shields.io/github/stars/kaminoguo/OfferI_Public?style=social)](https://github.com/kaminoguo/OfferI_Public)

Built for international students worldwide

</div>
