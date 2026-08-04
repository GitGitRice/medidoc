"""Die Stelle, an der die Module zusammenkommen — und die einzige.

Pro Modul genau eine Zeile. Prefix und Tags stehen im Modul selbst, damit ein
neues Feature hier nichts umbaut und zwei Leute nicht in derselben Zeile
kollidieren.
"""

from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.patients.router import router as patients_router
from app.modules.users.router import router as users_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(patients_router)
api_router.include_router(users_router)
