from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import PromotionLink, PromotionLinkClick

router = APIRouter(prefix="/links", tags=["promotion-links"])

SessionDep = Annotated[Session, Depends(get_db)]


@router.get("/r/{short_code}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
def redirect_short_link(short_code: str, request: Request, db: SessionDep) -> RedirectResponse:
    """处理重定向短链链接接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    promotion_link = db.scalars(
        select(PromotionLink).where(
            PromotionLink.short_code == short_code,
            PromotionLink.status == "active",
        )
    ).first()
    if promotion_link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion link not found")

    # 点击记录只保存归因所需的 referer/user-agent 摘要，不采集个人身份信息。
    click = PromotionLinkClick(
        product_id=promotion_link.product_id,
        promotion_link_id=promotion_link.id,
        tracking_code=promotion_link.tracking_code,
        referer=request.headers.get("referer"),
        user_agent=request.headers.get("user-agent"),
    )
    promotion_link.click_count += 1
    db.add(click)
    db.commit()

    # 短链只做跳转和计数，不触发广告投放、扣费或库存变化。
    return RedirectResponse(
        url=promotion_link.tracking_url or promotion_link.url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
