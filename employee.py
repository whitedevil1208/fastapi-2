import os
from fastapi import FastAPI, Depends, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from passlib.context import CryptContext
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Initialize FastAPI
app = FastAPI()

# CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Models
class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    employees = relationship("Employee", back_populates="company")

class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    company = Column(String(255), ForeignKey("companies.name", ondelete="CASCADE"), nullable=False)
    role = Column(String(100), nullable=False)
    password_hash = Column(Text, nullable=False)

    company_rel = relationship("Company", back_populates="employees")

# Create tables
Base.metadata.create_all(bind=engine)

# Schemas
class EmployeeOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    company: str
    role: str

    class Config:
        orm_mode = True

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Utility
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

# Routes
@app.post("/employees", response_model=EmployeeOut)
def create_employee(
    name: str = Form(...),
    email: EmailStr = Form(...),
    company: str = Form(...),
    role: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    company_lower = company.lower()

    # Check if company exists
    existing_company = db.query(Company).filter(Company.name == company_lower).first()
    if not existing_company:
        raise HTTPException(status_code=404, detail="Company does not exist")

    # Check if employee email already used
    if db.query(Employee).filter(Employee.email == email).first():
        raise HTTPException(status_code=400, detail="Employee with this email already exists")

    # Hash password
    hashed_password = hash_password(password)

    # Create employee
    employee = Employee(
        name=name,
        email=email,
        company=company_lower,
        role=role,
        password_hash=hashed_password,
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee

@app.get("/employees", response_model=list[EmployeeOut])
def get_all_employees(db: Session = Depends(get_db)):
    return db.query(Employee).all()

@app.get("/employees/{employee_id}", response_model=EmployeeOut)
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    employee = db.query(Employee).get(employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee

@app.delete("/employees/{employee_id}", status_code=204)
def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    employee = db.query(Employee).get(employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    db.delete(employee)
    db.commit()
