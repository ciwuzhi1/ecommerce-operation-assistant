from datetime import datetime, timezone
from secrets import token_urlsafe
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.routes.auth import require_edit_permission, require_view_permission
from app.db.session import get_db
from app.models import InventoryItem, InventoryMovement, PlatformAccount, PlatformAccountStatus, Product, ProductSku, Store, User
from app.schemas import (
    PlatformAccountCreate,
    PlatformAccountRead,
    PlatformAuthorizationCallbackRequest,
    PlatformAuthorizationRead,
    PlatformAuthorizationStartRequest,
    StoreCreate,
    StoreInventoryAdviceRead,
    StoreInventoryRow,
    StoreInventoryMovementRow,
    StoreInventorySummary,
    StoreRead,
    StoreUpdate,
)


from app.services.inventory_advice import generate_inventory_advice

router = APIRouter(prefix="/stores", tags=["stores"])
SessionDep = Annotated[Session, Depends(get_db)]


def get_store_or_404(db: Session, store_id: int) -> Store:
    """处理获取店铺or404接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    store = db.get(Store, store_id)
    workspace_id = db.info.get("workspace_id")
    if store is None or (workspace_id is not None and store.workspace_id != workspace_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    return store


def get_platform_account_or_404(db: Session, store_id: int, account_id: int) -> PlatformAccount:
    """处理获取平台账号or404接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    account = db.get(PlatformAccount, account_id)
    if account is None or account.store_id != store_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform account not found")
    return account


@router.get("", response_model=list[StoreRead])
def list_stores(
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_view_permission)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[Store]:
    """处理查询stores接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    statement = select(Store).options(selectinload(Store.platform_accounts))
    workspace_id = db.info.get("workspace_id")
    if workspace_id is not None:
        statement = statement.where(Store.workspace_id == workspace_id)
    statement = statement.order_by(Store.created_at.desc()).offset(offset).limit(limit)
    return list(db.scalars(statement).all())


@router.post("", response_model=StoreRead, status_code=status.HTTP_201_CREATED)
def create_store(
    payload: StoreCreate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> Store:
    """处理创建店铺接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    store = Store(workspace_id=db.info.get("workspace_id"), **payload.model_dump(mode="json"))
    db.add(store)
    db.commit()
    db.refresh(store)
    return store


@router.get("/{store_id}", response_model=StoreRead)
def get_store(
    store_id: int,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_view_permission)],
) -> Store:
    """处理获取店铺接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    statement = (
        select(Store)
        .where(Store.id == store_id)
        .options(selectinload(Store.platform_accounts))
    )
    workspace_id = db.info.get("workspace_id")
    if workspace_id is not None:
        statement = statement.where(Store.workspace_id == workspace_id)
    store = db.scalars(statement).first()
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    return store


@router.get("/{store_id}/inventory-summary", response_model=StoreInventorySummary)
def get_store_inventory_summary(
    store_id: int,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_view_permission)],
) -> StoreInventorySummary:
    """处理获取店铺库存汇总接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_store_or_404(db, store_id)
    rows = build_store_inventory_rows(db, store_id)

    return StoreInventorySummary(
        store_id=store_id,
        sku_count=len(rows),
        total_quantity=sum(row.quantity for row in rows),
        total_locked_quantity=sum(row.locked_quantity for row in rows),
        total_available_quantity=sum(row.available_quantity for row in rows),
        low_stock_count=sum(1 for row in rows if row.is_low_stock),
        rows=rows,
    )


@router.post("/{store_id}/inventory-advice", response_model=StoreInventoryAdviceRead)
def generate_store_inventory_advice(
    store_id: int,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> StoreInventoryAdviceRead:
    """处理生成店铺库存建议接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    store = get_store_or_404(db, store_id)
    rows = build_store_inventory_rows(db, store_id)
    return StoreInventoryAdviceRead.model_validate(generate_inventory_advice(store, rows))


@router.get("/{store_id}/inventory-movements", response_model=list[StoreInventoryMovementRow])
def list_store_inventory_movements(
    store_id: int,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_view_permission)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[StoreInventoryMovementRow]:
    """处理查询店铺库存movements接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_store_or_404(db, store_id)
    statement = (
        select(InventoryMovement, ProductSku, Product)
        .join(ProductSku, InventoryMovement.sku_id == ProductSku.id)
        .join(Product, ProductSku.product_id == Product.id)
        .where(Product.store_id == store_id)
        .order_by(InventoryMovement.created_at.desc(), InventoryMovement.id.desc())
        .limit(limit)
    )

    return [
        StoreInventoryMovementRow(
            id=movement.id,
            product_id=product.id,
            product_name=product.name,
            sku_id=sku.id,
            sku_code=sku.sku_code,
            sku_name=sku.name,
            movement_type=movement.movement_type,
            quantity_delta=movement.quantity_delta,
            locked_delta=movement.locked_delta,
            before_quantity=movement.before_quantity,
            after_quantity=movement.after_quantity,
            before_locked_quantity=movement.before_locked_quantity,
            after_locked_quantity=movement.after_locked_quantity,
            reason=movement.reason,
            operator_name=movement.operator_name,
            created_at=movement.created_at,
        )
        for movement, sku, product in db.execute(statement).all()
    ]


def build_store_inventory_rows(db: Session, store_id: int) -> list[StoreInventoryRow]:
    """处理构建店铺库存行接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    statement = (
        select(ProductSku, Product, InventoryItem)
        .join(Product, ProductSku.product_id == Product.id)
        .outerjoin(InventoryItem, InventoryItem.sku_id == ProductSku.id)
        .where(Product.store_id == store_id)
        .order_by(Product.created_at.desc(), ProductSku.created_at.desc())
    )

    rows: list[StoreInventoryRow] = []
    for sku, product, inventory_item in db.execute(statement).all():
        quantity = inventory_item.quantity if inventory_item else 0
        locked_quantity = inventory_item.locked_quantity if inventory_item else 0
        warning_threshold = inventory_item.warning_threshold if inventory_item else 0
        available_quantity = quantity - locked_quantity
        # 库存建议只做风险识别和运营提醒，不直接修改库存；真实变化必须走库存流水。
        is_low_stock = warning_threshold > 0 and available_quantity <= warning_threshold
        rows.append(
            StoreInventoryRow(
                product_id=product.id,
                product_name=product.name,
                sku_id=sku.id,
                sku_code=sku.sku_code,
                sku_name=sku.name,
                quantity=quantity,
                locked_quantity=locked_quantity,
                available_quantity=available_quantity,
                warning_threshold=warning_threshold,
                is_low_stock=is_low_stock,
                location=inventory_item.location if inventory_item else None,
            )
        )
    return rows


@router.patch("/{store_id}", response_model=StoreRead)
def update_store(
    store_id: int,
    payload: StoreUpdate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> Store:
    """处理更新店铺接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    store = get_store_or_404(db, store_id)
    for field, value in payload.model_dump(exclude_unset=True, mode="json").items():
        setattr(store, field, value)
    db.commit()
    db.refresh(store)
    return store


@router.post(
    "/{store_id}/platform-accounts",
    response_model=PlatformAccountRead,
    status_code=status.HTTP_201_CREATED,
)
def create_platform_account(
    store_id: int,
    payload: PlatformAccountCreate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> PlatformAccount:
    """处理创建平台账号接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    store = get_store_or_404(db, store_id)
    account = PlatformAccount(store_id=store.id, **payload.model_dump(mode="json"))
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.post(
    "/{store_id}/platform-accounts/{account_id}/authorization/start",
    response_model=PlatformAuthorizationRead,
)
def start_platform_authorization(
    store_id: int,
    account_id: int,
    payload: PlatformAuthorizationStartRequest,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> PlatformAuthorizationRead:
    """处理启动平台授权接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    account = get_platform_account_or_404(db, store_id, account_id)
    state = token_urlsafe(24)
    now = datetime.now(timezone.utc)
    metadata = dict(account.auth_metadata or {})
    # V1 只预留授权流程合同，不保存平台密码、Cookie 或 access token，后续接官方 OAuth/API 时再接入密钥托管。
    metadata["authorization"] = {
        "status": "pending",
        "auth_type": payload.auth_type,
        "state": state,
        "redirect_uri": str(payload.redirect_uri) if payload.redirect_uri else None,
        "callback_url": str(payload.callback_url) if payload.callback_url else None,
        "scopes": payload.scopes,
        "note": payload.note,
        "requested_at": now.isoformat(),
        "safety_boundary": "仅支持官方 API、服务商 API、用户授权或用户导出的数据，不实现绕过登录/验证码/风控的采集。",
    }
    account.auth_metadata = metadata
    db.commit()
    db.refresh(account)
    return _authorization_read(account)


@router.post(
    "/{store_id}/platform-accounts/{account_id}/authorization/callback-placeholder",
    response_model=PlatformAuthorizationRead,
)
def record_platform_authorization_callback(
    store_id: int,
    account_id: int,
    payload: PlatformAuthorizationCallbackRequest,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> PlatformAuthorizationRead:
    """处理记录平台授权callback接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    account = get_platform_account_or_404(db, store_id, account_id)
    metadata = dict(account.auth_metadata or {})
    authorization = dict(metadata.get("authorization") or {})
    if authorization.get("state") != payload.state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authorization state mismatch")

    now = datetime.now(timezone.utc)
    # 回调占位接口只记录授权结果和非敏感元数据；真实 token 后续应接入密钥管理或服务商托管。
    authorization.update(
        {
            "status": payload.status,
            "external_account_id": payload.external_account_id,
            "provider_metadata": payload.metadata,
            "note": payload.note,
            "updated_at": now.isoformat(),
        }
    )
    metadata["authorization"] = authorization
    account.auth_metadata = metadata
    if payload.external_account_id:
        account.external_account_id = payload.external_account_id
    account.status = _account_status_from_authorization(payload.status)
    db.commit()
    db.refresh(account)
    return _authorization_read(account)


def _account_status_from_authorization(auth_status: str) -> PlatformAccountStatus:
    """处理账号状态from授权接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    if auth_status == "authorized":
        return PlatformAccountStatus.ACTIVE
    if auth_status == "expired":
        return PlatformAccountStatus.EXPIRED
    return PlatformAccountStatus.DISABLED


def _authorization_read(account: PlatformAccount) -> PlatformAuthorizationRead:
    """处理授权读取接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    authorization = dict((account.auth_metadata or {}).get("authorization") or {})
    auth_status = authorization.get("status") or "pending"
    auth_type = authorization.get("auth_type") or "oauth2"
    state = authorization.get("state")
    return PlatformAuthorizationRead(
        account_id=account.id,
        platform=account.platform,
        status=auth_status,
        auth_type=auth_type,
        state=state,
        authorization_url=_authorization_url(account, authorization),
        next_action=_authorization_next_action(auth_status),
        safety_note="请使用平台开放 API、服务商 API、用户授权或用户导出的报表；不要绕过登录、验证码或风控。",
        updated_at=account.updated_at,
    )


def _authorization_url(account: PlatformAccount, authorization: dict) -> str | None:
    """处理授权URL接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    redirect_uri = authorization.get("redirect_uri")
    state = authorization.get("state")
    if not redirect_uri or not state:
        return None
    return f"{redirect_uri}?platform={account.platform.value}&account_id={account.id}&state={state}"


def _authorization_next_action(auth_status: str) -> str:
    """处理授权下次action接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    if auth_status == "pending":
        return "前往平台官方授权页或服务商后台完成授权，然后调用占位回调接口记录结果。"
    if auth_status == "authorized":
        return "授权已记录，后续可以接入官方数据同步任务。"
    if auth_status == "expired":
        return "授权已过期，请重新发起授权。"
    return "授权不可用，请检查平台账号状态或重新授权。"
