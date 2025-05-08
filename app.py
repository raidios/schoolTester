from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import random
import json
import logging
from typing import List, Optional
from pydantic import BaseModel, ValidationError

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(title="三年级数学练习")

# 数据库配置
SQLALCHEMY_DATABASE_URL = "sqlite:///./math_practice.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 数据库模型
class PracticeRecord(Base):
    __tablename__ = "practice_records"

    id = Column(Integer, primary_key=True, index=True)
    start_time = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String)
    total_questions = Column(Integer)
    completed_questions = Column(Integer)
    correct_count = Column(Integer)
    accuracy = Column(Float)
    total_time = Column(String)
    wrong_questions = Column(JSON)

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 设置模板目录
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Question(BaseModel):
    num1: int
    num2: int
    operation: str
    answer: int

class GameConfig(BaseModel):
    total_questions: int
    time_limit: int

class GameResult(BaseModel):
    correct_count: int
    total_questions: int
    wrong_questions: List[dict]

class PracticeResult(BaseModel):
    total_questions: int
    completed_questions: int
    correct_count: int
    accuracy: float
    total_time: str
    wrong_questions: List[dict]

    class Config:
        schema_extra = {
            "example": {
                "total_questions": 10,
                "completed_questions": 8,
                "correct_count": 7,
                "accuracy": 70.0,
                "total_time": "05:30",
                "wrong_questions": [
                    {
                        "num1": 5,
                        "num2": 3,
                        "operation": "+",
                        "answer": 8,
                        "userAnswer": 7
                    }
                ]
            }
        }

def generate_question() -> dict:
    """生成一道适合三年级学生的数学题"""
    operations = ['+', '-', '*', '/']
    operation = random.choice(operations)
    
    if operation == '+':
        num1 = random.randint(100, 999)
        num2 = random.randint(100, 999)
        answer = num1 + num2
    elif operation == '-':
        num1 = random.randint(100, 999)
        num2 = random.randint(100, num1)
        answer = num1 - num2
    elif operation == '*':
        num1 = random.randint(1, 12)
        num2 = random.randint(1, 12)
        answer = num1 * num2
    else:  # 除法
        num2 = random.randint(1, 12)
        answer = random.randint(1, 12)
        num1 = num2 * answer
    
    return {
        'num1': num1,
        'num2': num2,
        'operation': operation,
        'answer': answer
    }

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("start.html", {"request": request})

@app.get("/game", response_class=HTMLResponse)
async def game(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/summary", response_class=HTMLResponse)
async def summary(request: Request):
    return templates.TemplateResponse("summary.html", {"request": request})

@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request):
    return templates.TemplateResponse("stats.html", {"request": request})

@app.get("/api/question")
async def get_question() -> Question:
    return generate_question()

@app.get("/api/questions")
async def get_questions():
    questions = []
    for _ in range(10):
        num1 = random.randint(1, 100)
        num2 = random.randint(1, 100)
        operation = random.choice(["+", "-", "*", "/"])
        
        if operation == "+":
            answer = num1 + num2
        elif operation == "-":
            answer = num1 - num2
        elif operation == "*":
            answer = num1 * num2
        else:  # division
            answer = num1 // num2
            num1 = num2 * answer  # 确保除法结果是整数
        
        questions.append({
            "num1": num1,
            "num2": num2,
            "operation": operation,
            "answer": answer
        })
    return questions

@app.post("/api/record")
async def record_practice(result: PracticeResult, request: Request):
    try:
        # 记录接收到的数据
        logger.debug(f"接收到的数据: {result.dict()}")
        
        client_host = request.client.host
        db = SessionLocal()
        try:
            # 计算正确率（使用总题数作为分母）
            accuracy = (result.correct_count / result.total_questions) * 100 if result.total_questions > 0 else 0
            
            record = PracticeRecord(
                ip_address=client_host,
                total_questions=result.total_questions,
                completed_questions=result.completed_questions,
                correct_count=result.correct_count,
                accuracy=accuracy,
                total_time=result.total_time,
                wrong_questions=result.wrong_questions
            )
            db.add(record)
            db.commit()
            logger.info(f"成功保存记录: {record.id}")
            return {"status": "success", "message": "记录已保存"}
        except Exception as e:
            db.rollback()
            logger.error(f"数据库错误: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"数据库错误: {str(e)}")
        finally:
            db.close()
    except ValidationError as e:
        logger.error(f"数据验证错误: {str(e)}", exc_info=True)
        logger.error(f"错误详情: {e.errors()}")
        raise HTTPException(status_code=422, detail={
            "message": "数据验证错误",
            "errors": e.errors()
        })
    except Exception as e:
        logger.error(f"服务器错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")

@app.get("/api/stats")
async def get_stats(start_date: Optional[str] = None, end_date: Optional[str] = None):
    db = SessionLocal()
    try:
        query = db.query(PracticeRecord)
        
        if start_date:
            query = query.filter(PracticeRecord.start_time >= datetime.fromisoformat(start_date))
        if end_date:
            query = query.filter(PracticeRecord.start_time <= datetime.fromisoformat(end_date + " 23:59:59"))
        
        records = query.order_by(PracticeRecord.start_time.desc()).all()
        
        return [
            {
                "start_time": record.start_time.isoformat(),
                "ip_address": record.ip_address,
                "total_questions": record.total_questions,
                "completed_questions": record.completed_questions,
                "correct_count": record.correct_count,
                "accuracy": record.accuracy,
                "total_time": record.total_time,
                "wrong_questions": record.wrong_questions
            }
            for record in records
        ]
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 