"""
Markdown to HTML Processor

Converts Markdown reports to styled HTML using Jinja2 templates.
"""

import markdown
import logging
from pathlib import Path
from typing import Dict, Any
from jinja2 import Environment, FileSystemLoader, select_autoescape

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MarkdownProcessor:
    """
    Converts Markdown to styled HTML for web preview and PDF generation.
    """

    def __init__(self, template_dir: str = None):
        """
        Initialize Markdown processor.

        Args:
            template_dir: Path to Jinja2 templates directory
                         (default: backend/templates/)
        """
        if template_dir is None:
            # Default to backend/templates/
            backend_dir = Path(__file__).parent.parent
            template_dir = str(backend_dir / "templates")

        self.template_dir = template_dir

        # Setup Jinja2 environment
        try:
            self.jinja_env = Environment(
                loader=FileSystemLoader(template_dir),
                autoescape=select_autoescape(['html', 'xml'])
            )
            logger.info(f"✅ Jinja2 templates loaded from {template_dir}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to load Jinja2 templates: {str(e)}")
            self.jinja_env = None

        # Configure Markdown extensions for rich formatting
        self.md_extensions = [
            'extra',           # Tables, fenced code blocks, etc.
            'codehilite',      # Syntax highlighting
            'toc',             # Table of contents
            'nl2br',           # Newline to <br>
            'sane_lists',      # Better list handling
        ]

        self.md = markdown.Markdown(extensions=self.md_extensions)

    def convert_markdown(self, markdown_text: str) -> str:
        """
        Convert Markdown to HTML (without template).

        Args:
            markdown_text: Raw Markdown string

        Returns:
            HTML string
        """
        try:
            # Reset Markdown processor (important for multiple conversions)
            self.md.reset()

            # Convert Markdown to HTML
            html = self.md.convert(markdown_text)

            return html

        except Exception as e:
            logger.error(f"❌ Markdown conversion failed: {str(e)}")
            raise

    def convert_to_html(
        self,
        markdown_text: str,
        use_template: bool = True,
        template_name: str = "report_template.html"
    ) -> Dict[str, Any]:
        """
        Convert Markdown to styled HTML using template.

        Args:
            markdown_text: Raw Markdown string
            use_template: Whether to use Jinja2 template (default: True)
            template_name: Template filename (default: report_template.html)

        Returns:
            Dict with 'success', 'html', 'error' keys
        """
        try:
            # Step 1: Convert Markdown to HTML
            content_html = self.convert_markdown(markdown_text)

            # Step 2: Apply template (if enabled)
            if use_template and self.jinja_env:
                try:
                    template = self.jinja_env.get_template(template_name)
                    final_html = template.render(
                        content=content_html,
                        title="OfferI 留学申请分析报告"
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Template render failed, using plain HTML: {str(e)}")
                    final_html = self._wrap_html_basic(content_html)
            else:
                final_html = self._wrap_html_basic(content_html)

            logger.info(f"✅ Converted Markdown to HTML ({len(final_html)} chars)")

            return {
                "success": True,
                "html": final_html,
                "error": None
            }

        except Exception as e:
            logger.error(f"❌ HTML conversion failed: {str(e)}")
            return {
                "success": False,
                "html": None,
                "error": str(e)
            }

    def _wrap_html_basic(self, content: str) -> str:
        """
        Wrap HTML content in basic template (fallback).

        Args:
            content: HTML content

        Returns:
            Complete HTML document
        """
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OfferI 留学申请分析报告</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 0 auto;
            padding: 40px 20px;
            color: #333;
            background: #f9f9f9;
        }}
        h1 {{
            color: #2563eb;
            border-bottom: 3px solid #2563eb;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #1e40af;
            margin-top: 30px;
            border-left: 4px solid #2563eb;
            padding-left: 15px;
        }}
        h3 {{
            color: #1e3a8a;
        }}
        code {{
            background: #f1f5f9;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: "Courier New", monospace;
        }}
        pre {{
            background: #1e293b;
            color: #e2e8f0;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #e2e8f0;
            padding: 10px;
            text-align: left;
        }}
        th {{
            background: #f1f5f9;
            font-weight: 600;
        }}
        blockquote {{
            border-left: 4px solid #94a3b8;
            padding-left: 15px;
            color: #64748b;
            margin: 20px 0;
        }}
        a {{
            color: #2563eb;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        ul, ol {{
            margin: 15px 0;
        }}
        li {{
            margin: 5px 0;
        }}
        hr {{
            border: none;
            border-top: 2px solid #e2e8f0;
            margin: 30px 0;
        }}
    </style>
</head>
<body>
    {content}
</body>
</html>"""


# Example usage
if __name__ == "__main__":
    processor = MarkdownProcessor()

    # Test Markdown
    test_md = """# 留学申请分析报告

## 👤 背景评估

### 学术背景
- **本科院校**: HKUST (QS 44)
- **GPA**: 3.5/4.0
- **专业**: CS + AI

### 经历亮点
1. 推荐系统项目经验
2. Google 实习 3 个月
3. 产品经理职业目标

## 🎯 项目推荐

### 1. CMU MISM - 卡内基梅隆大学

**基本信息**
- 🏫 **院校**: CMU (US #3)
- 📍 **地点**: Pittsburgh, USA
- 💰 **学费**: $60,000/year
- ⏱️ **学制**: 16 months

**推荐理由**
技术背景强，适合转产品管理，就业率高。

---

## 📊 申请策略建议

### 项目组合
- **冲刺**: CMU, Stanford, MIT
- **匹配**: UCSD, USC, GaTech
- **保底**: NCSU, UCI, UMass
"""

    result = processor.convert_to_html(test_md, use_template=False)

    if result["success"]:
        print("✅ HTML generated successfully!")
        print(f"Length: {len(result['html'])} chars")

        # Save to file
        output_path = Path(__file__).parent.parent / "test_report.html"
        output_path.write_text(result["html"], encoding="utf-8")
        print(f"Saved to: {output_path}")
    else:
        print(f"❌ Error: {result['error']}")
