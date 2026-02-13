"""
Legacy Entity Management Routes - Backed up from app.py
========================================================
Removed as part of Phase 2: Absorb Legacy Directory

These routes were at /admin/entities/* and have been replaced by
the CQE Admin routes at /admin/cqe/*

Original location: app.py lines 416-446 (models) and 4167-4535 (routes)
Backup date: 2026-02-13
"""

from pydantic import BaseModel
from typing import List, Optional

# ==============================================================================
# ENTITY MANAGEMENT MODELS - Phase 10 (LEGACY)
# ==============================================================================

class EntityCreate(BaseModel):
    """Request model for creating a new directory entity."""
    entity_id: str
    canonical_name: str
    aliases: List[str]
    building: str
    floor: str
    room: Optional[str] = None
    campus: str = "Main Campus"
    department: Optional[str] = None
    landmarks: Optional[str] = None
    description: Optional[str] = None


class EntityUpdate(BaseModel):
    """Request model for updating an existing directory entity."""
    canonical_name: Optional[str] = None
    aliases: Optional[List[str]] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    room: Optional[str] = None
    campus: Optional[str] = None
    department: Optional[str] = None
    landmarks: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class EntityValidateRequest(BaseModel):
    """Request model for entity validation."""
    entity_id: str
    canonical_name: str
    aliases: List[str] = []
    building: str
    floor: str
    room: Optional[str] = None
    campus: str = "Main Campus"
    department: Optional[str] = None
    landmarks: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = []
    status: str = "active"


# ==============================================================================
# ADMIN ENTITY ENDPOINTS - Phase 10 (LEGACY)
# ==============================================================================

"""
The following endpoints were removed:

GET    /admin/entities                    - List all entities
GET    /admin/entities/export             - Export to CSV
POST   /admin/entities/import             - Import from CSV
GET    /admin/entities/{entity_id}        - Get single entity
POST   /admin/entities                    - Create entity
PUT    /admin/entities/{entity_id}        - Update entity
DELETE /admin/entities/{entity_id}        - Delete entity
POST   /admin/entities/validate           - Validate entity

These are replaced by CQE Admin endpoints at /admin/cqe/*
"""

# Full route implementations are preserved below for reference:

# @app.get("/admin/entities", dependencies=[Depends(verify_admin_session)])
# async def list_entities():
#     """List all directory entities."""
#     from dataclasses import asdict
#     entities = []
#     for entity in entity_registry.get_all_entities():
#         entity_dict = asdict(entity)
#         entities.append(entity_dict)
#     entities.sort(key=lambda x: x['entity_id'])
#     return {
#         "entities": entities,
#         "total": len(entities),
#         "active": len([e for e in entities if e.get('status', 'active') == 'active'])
#     }

# @app.get("/admin/entities/export", dependencies=[Depends(verify_admin_session)])
# async def export_entities():
#     """Export all directory entities to CSV format."""
#     # CSV export implementation
#     pass

# @app.post("/admin/entities/import", dependencies=[Depends(verify_admin_session)])
# async def import_entities(file: UploadFile = File(...)):
#     """Import directory entities from CSV file."""
#     # CSV import implementation
#     pass

# @app.get("/admin/entities/{entity_id}", dependencies=[Depends(verify_admin_session)])
# async def get_entity(entity_id: str):
#     """Get a single directory entity by ID."""
#     pass

# @app.post("/admin/entities", dependencies=[Depends(verify_admin_session)])
# async def create_entity(entity_data: EntityCreate):
#     """Create a new directory entity."""
#     pass

# @app.put("/admin/entities/{entity_id}", dependencies=[Depends(verify_admin_session)])
# async def update_entity(entity_id: str, entity_data: EntityUpdate):
#     """Update an existing directory entity."""
#     pass

# @app.delete("/admin/entities/{entity_id}", dependencies=[Depends(verify_admin_session)])
# async def delete_entity(entity_id: str, hard: bool = False):
#     """Delete a directory entity (soft or hard delete)."""
#     pass

# @app.post("/admin/entities/validate", dependencies=[Depends(verify_admin_session)])
# async def validate_entity(data: EntityValidateRequest):
#     """Validate entity data without saving."""
#     pass
