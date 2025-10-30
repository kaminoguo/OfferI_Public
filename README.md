<div align="center">

# OfferI

### AI-Powered Study Abroad Consultation Platform

*Personalized master's program recommendations using Claude Code and MCP*

[🌐 Website](https://offeri.org) · [📺 Bilibili](#) · [🎬 YouTube](#) · [Issues](https://github.com/kaminoguo/OfferI_Public/issues)

</div>

---

## Overview

**OfferI** is an AI-powered study abroad consultation platform that provides personalized master's program recommendations from a curated database of **60,000+ high-quality programs** from top universities worldwide.

Unlike traditional consultants charging $2,000-5,000, OfferI delivers professional analysis for **$6 per consultation**, with reports generated in **10-15 minutes**.

### Current Focus

**Master's Programs Only** (MVP Phase)

After validating product-market fit, we plan to expand to:
- Bachelor's programs
- PhD programs (including professor recommendations)
- Non-English taught programs

---

## Demo Videos

### Web Service Demo
> 📺 **Video coming soon** - Full consultation flow demonstration

<!-- Placeholder for web service demo video -->
*Watch how users get personalized program recommendations in 10-15 minutes*

### MCP Service Demo
> 🎬 **Video coming soon** - Using OfferI MCP in Claude Desktop/Code

<!-- Placeholder for MCP service demo video -->
*See how developers can integrate OfferI database into their AI applications*

---

## Technical Architecture

### Core Technical Advantages

**1. MCP Direct Database Access → Lower Hallucination Rate**

Unlike RAG (Retrieval-Augmented Generation) which uses vector similarity matching, we use **MCP (Model Context Protocol) for direct SQL queries**:

- **RAG Approach**: Text → Embeddings → Vector Search → ~85% semantic accuracy (hallucination risk)
- **Our Approach**: MCP → Direct SQL Query → 100% deterministic results (zero hallucination)

For structured data like university programs (name, tuition, duration), SQL is inherently more reliable than semantic similarity.

**2. Using Official CLI Tools → Product Improves Automatically**

We use **official CLI tools from major vendors** (Claude Code, Gemini CLI, Context7):

- **Our Advantage**: When vendors update their CLIs, our product gets better automatically
- **LangChain/LangGraph Risk**: Framework abstractions can break with LLM updates, requiring constant maintenance
- **Multi-vendor Testing**: We've tested Claude Code CLI, Gemini CLI, and Context7 to ensure flexibility

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
- Claude Pro OAuth authentication
- MCP (Model Context Protocol)
- Single-stage pipeline (Claude Sonnet 4.5)

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
- Free tier: 5 consultations per month (one consultation = multiple API calls)

**Step 2: Configure Your MCP Client**

Our MCP server works with any MCP-compatible client. Choose your platform below:

<details>
<summary><b>Claude Desktop</b> - Click to expand</summary>

Edit your config file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

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

Restart Claude Desktop after saving.

</details>

<details>
<summary><b>Claude Code CLI</b> - Click to expand</summary>

```bash
# Add OfferI MCP server with your API key
claude mcp add offeri https://api.offeri.org/mcp --transport http -H "Authorization: Bearer sk_live_YOUR_API_KEY_HERE"

# Verify connection
claude mcp list
```

</details>

<details>
<summary><b>Gemini CLI</b> - Click to expand</summary>

```bash
# Add OfferI MCP server
gemini mcp add offeri https://api.offeri.org/mcp

# Verify connection
gemini mcp list
```

**Note**: Gemini CLI currently does not support HTTP headers for authentication. Use the free tier (5 consultations/month) or switch to Claude Desktop/Code for authenticated access.

</details>

<details>
<summary><b>Context7 / Other MCP Clients</b> - Click to expand</summary>

For other MCP-compatible clients, add the following configuration:

```json
{
  "mcpServers": {
    "offeri": {
      "type": "http",
      "url": "https://api.offeri.org/mcp",
      "headers": {
        "Authorization": "Bearer sk_live_YOUR_API_KEY_HERE"
      }
    }
  }
}
```

Or if your client doesn't support authentication headers, use without the `headers` field for free tier access.

</details>

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

Built for international students worldwide

</div>
