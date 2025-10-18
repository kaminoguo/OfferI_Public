"""
PDF Generator

Converts HTML reports to PDF using WeasyPrint.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PDFGenerator:
    """
    Generates PDF files from HTML content.
    Uses WeasyPrint for high-quality PDF rendering.
    """

    def __init__(self, output_dir: str = None):
        """
        Initialize PDF generator.

        Args:
            output_dir: Directory to save PDF files
                       (default: backend/outputs/)
        """
        if output_dir is None:
            # Default to backend/outputs/
            backend_dir = Path(__file__).parent.parent
            output_dir = str(backend_dir / "outputs")

        self.output_dir = Path(output_dir)

        # Create output directory if not exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"✅ PDF output directory: {self.output_dir}")

        # Font configuration for WeasyPrint
        self.font_config = FontConfiguration()

        # Custom CSS for PDF styling - Minimal Black/White
        self.pdf_css = CSS(string="""
            @page {
                size: A4;
                margin: 2cm;
            }

            body {
                font-family: "Microsoft YaHei", "SimHei", "STHeiti", "PingFang SC", sans-serif;
                font-size: 11pt;
                line-height: 1.6;
                color: #000000;
            }

            h1 {
                font-size: 22pt;
                color: #000000;
                font-weight: 700;
                border-bottom: 2px solid #000000;
                padding-bottom: 8px;
                margin: 30px 0 20px 0;
                page-break-after: avoid;
            }

            h2 {
                font-size: 16pt;
                color: #000000;
                font-weight: 600;
                margin: 25px 0 15px 0;
                page-break-after: avoid;
            }

            h3 {
                font-size: 13pt;
                color: #000000;
                font-weight: 600;
                margin: 20px 0 12px 0;
                page-break-after: avoid;
            }

            p {
                margin: 10px 0;
                color: #000000;
                orphans: 3;
                widows: 3;
            }

            ul, ol {
                margin: 12px 0;
                padding-left: 30px;
            }

            li {
                margin: 6px 0;
                line-height: 1.5;
            }

            table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
                page-break-inside: avoid;
            }

            th {
                border: 1px solid #000000;
                padding: 10px;
                text-align: left;
                font-weight: 600;
                background: #f0f0f0;
                color: #000000;
            }

            td {
                border: 1px solid #000000;
                padding: 10px;
                text-align: left;
                color: #000000;
            }

            tbody tr:nth-child(even) {
                background: #fafafa;
            }

            tbody tr:nth-child(odd) {
                background: #ffffff;
            }

            code {
                background: #f5f5f5;
                color: #000000;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: "Courier New", Consolas, monospace;
                font-size: 10pt;
            }

            pre {
                background: #f5f5f5;
                color: #000000;
                padding: 15px;
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                overflow-x: auto;
                margin: 15px 0;
                page-break-inside: avoid;
            }

            pre code {
                background: transparent;
                color: #000000;
                padding: 0;
            }

            blockquote {
                border-left: 3px solid #000000;
                padding: 10px 0 10px 15px;
                color: #000000;
                margin: 15px 0;
                font-style: italic;
            }

            a {
                color: #000000;
                text-decoration: underline;
            }

            hr {
                border: none;
                border-top: 1px solid #000000;
                margin: 25px 0;
            }

            strong, b {
                font-weight: 700;
                color: #000000;
            }

            em, i {
                font-style: italic;
            }

            /* Avoid page breaks inside important elements */
            .no-break {
                page-break-inside: avoid;
            }
        """, font_config=self.font_config)

    def generate_pdf(
        self,
        html_content: str,
        job_id: str,
        filename: str = None
    ) -> Dict[str, Any]:
        """
        Generate PDF from HTML content.

        Args:
            html_content: Complete HTML document string
            job_id: Job identifier (used for default filename)
            filename: Custom filename (optional, default: report_{job_id}.pdf)

        Returns:
            Dict with 'success', 'pdf_path', 'error' keys
        """
        try:
            # Generate filename
            if filename is None:
                filename = f"report_{job_id}.pdf"

            # Ensure .pdf extension
            if not filename.endswith(".pdf"):
                filename += ".pdf"

            pdf_path = self.output_dir / filename

            logger.info(f"🔄 Generating PDF: {filename}")

            # Convert HTML to PDF
            html_doc = HTML(string=html_content)
            html_doc.write_pdf(
                pdf_path,
                stylesheets=[self.pdf_css],
                font_config=self.font_config
            )

            # Verify PDF was created
            if not pdf_path.exists():
                raise FileNotFoundError("PDF file was not created")

            # Get file size
            file_size = pdf_path.stat().st_size
            file_size_mb = file_size / (1024 * 1024)

            logger.info(f"✅ PDF generated: {filename} ({file_size_mb:.2f} MB)")

            return {
                "success": True,
                "pdf_path": str(pdf_path),
                "file_size": file_size,
                "error": None
            }

        except Exception as e:
            logger.error(f"❌ PDF generation failed: {str(e)}")
            return {
                "success": False,
                "pdf_path": None,
                "file_size": 0,
                "error": str(e)
            }

    def delete_pdf(self, pdf_path: str) -> bool:
        """
        Delete PDF file.

        Args:
            pdf_path: Path to PDF file

        Returns:
            True if successful, False otherwise
        """
        try:
            path = Path(pdf_path)
            if path.exists():
                path.unlink()
                logger.info(f"✅ Deleted PDF: {pdf_path}")
                return True
            else:
                logger.warning(f"⚠️ PDF not found: {pdf_path}")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to delete PDF: {str(e)}")
            return False

    def cleanup_old_pdfs(self, days: int = 7) -> int:
        """
        Delete PDF files older than specified days.

        Args:
            days: Age threshold in days

        Returns:
            Number of files deleted
        """
        try:
            import time

            deleted = 0
            threshold = time.time() - (days * 24 * 60 * 60)

            for pdf_file in self.output_dir.glob("*.pdf"):
                if pdf_file.stat().st_mtime < threshold:
                    pdf_file.unlink()
                    deleted += 1
                    logger.info(f"🗑️ Deleted old PDF: {pdf_file.name}")

            logger.info(f"✅ Cleaned up {deleted} old PDF files")
            return deleted

        except Exception as e:
            logger.error(f"❌ Failed to cleanup PDFs: {str(e)}")
            return 0


# Example usage
if __name__ == "__main__":
    generator = PDFGenerator()

    # Test HTML
    test_html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>OfferI 留学申请分析报告</title>
</head>
<body>
    <h1>留学申请分析报告</h1>

    <h2>👤 背景评估</h2>

    <h3>学术背景</h3>
    <ul>
        <li><strong>本科院校</strong>: HKUST (QS 44)</li>
        <li><strong>GPA</strong>: 3.5/4.0</li>
        <li><strong>专业</strong>: CS + AI</li>
    </ul>

    <h3>经历亮点</h3>
    <ol>
        <li>推荐系统项目经验</li>
        <li>Google 实习 3 个月</li>
        <li>产品经理职业目标</li>
    </ol>

    <hr>

    <h2>🎯 项目推荐</h2>

    <h3>1. CMU MISM - 卡内基梅隆大学</h3>

    <p><strong>基本信息</strong></p>
    <table>
        <tr>
            <th>项目</th>
            <td>Master of Information Systems Management</td>
        </tr>
        <tr>
            <th>院校</th>
            <td>CMU (US #3)</td>
        </tr>
        <tr>
            <th>地点</th>
            <td>Pittsburgh, USA</td>
        </tr>
        <tr>
            <th>学费</th>
            <td>$60,000/year</td>
        </tr>
        <tr>
            <th>学制</th>
            <td>16 months</td>
        </tr>
    </table>

    <p><strong>推荐理由</strong></p>
    <p>技术背景强，适合转产品管理，就业率高。</p>

    <hr>

    <h2>📊 申请策略建议</h2>

    <h3>项目组合</h3>
    <ul>
        <li><strong>冲刺</strong>: CMU, Stanford, MIT</li>
        <li><strong>匹配</strong>: UCSD, USC, GaTech</li>
        <li><strong>保底</strong>: NCSU, UCI, UMass</li>
    </ul>

    <blockquote>
        <p>💡 建议：重点准备 GMAT (700+) 和推荐信，突出技术+商业的复合背景。</p>
    </blockquote>
</body>
</html>"""

    result = generator.generate_pdf(test_html, "test-job-123")

    if result["success"]:
        print(f"✅ PDF generated: {result['pdf_path']}")
        print(f"File size: {result['file_size'] / 1024:.2f} KB")
    else:
        print(f"❌ Error: {result['error']}")
