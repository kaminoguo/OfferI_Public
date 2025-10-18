"""
Data models for OfferI Backend API
Supports unstructured user input - flexible and natural
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class UserBackground(BaseModel):
    """
    User background - RAW TEXT INPUT

    Frontend form helps users fill in their background,
    but submits as a single text field to API.

    Example:
    {
      "background": "我是香港科技大学ELEC+AI专业，绩点3.0，有3个月谷歌TPM实习..."
    }
    """
    background: str = Field(
        ...,
        description="Complete user background as free-form text (中英文均可)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "background": "我是香港科技大学ELEC+AI专业，绩点3.0，有3个月谷歌TPM实习，9个月OpenAI TPM实习，并提前一年毕业，有4个100star+的GitHub个人项目，每个都持续维护了一年以上，3个大型黑客松奖项，AI大牛的弱推一封，OpenAI的强推一封，我后面转产品以AI CPO为目标努力，只考虑香港、日本、美国的学校，预算无上限"
            }
        }


class JobSubmitResponse(BaseModel):
    """Response when user submits a job"""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status: queued")
    message: str = Field(..., description="User-friendly message")
    estimated_time: str = Field(..., description="Estimated completion time")


class JobStatusResponse(BaseModel):
    """Response when checking job status"""
    job_id: str
    status: str = Field(..., description="Job status: pending, processing, completed, failed")
    progress: Optional[str] = Field(None, description="Progress message (Chinese)")
    created_at: Optional[str] = Field(None, description="Job creation time")
    updated_at: Optional[str] = Field(None, description="Last update time")


class ProgramRecommendation(BaseModel):
    """Single program recommendation"""
    tier: str = Field(..., description="冲刺/匹配/保底")
    program_name: str
    university: str
    country: str
    tuition: str
    duration: str
    suitability_score: int = Field(..., ge=0, le=100)
    admission_difficulty: int = Field(..., ge=1, le=10)
    reasoning: str
    requirements: str
    deadline: Optional[str] = None
    url: str


class ReportResult(BaseModel):
    """Complete report result"""
    job_id: str
    status: str
    recommendations: List[ProgramRecommendation]
    summary: str
    analysis: str
    generated_at: str


class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    detail: Optional[str] = None
    job_id: Optional[str] = None
