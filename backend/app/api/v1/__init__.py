from fastapi import APIRouter
from app.api.v1 import auth, finance, ewa, ai, demo_ai, employers, employees, employments, salary, rbac, financial_context

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(finance.router)
api_router.include_router(ewa.router)
api_router.include_router(ai.router)
api_router.include_router(demo_ai.router)
api_router.include_router(employers.router)
api_router.include_router(employees.router)
api_router.include_router(employments.router)
api_router.include_router(salary.router)
api_router.include_router(rbac.router)
api_router.include_router(financial_context.router)
api_router.include_router(products.router)