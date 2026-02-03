"""Public router for orcazap.com and www.orcazap.com."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from decimal import Decimal

from app.core.dependencies import get_current_user, get_db
from app.core.onboarding_templates import render_onboarding_step
from app.core.sessions import create_session, delete_session
from app.core.stripe import create_checkout_session, is_subscription_active
from app.core.templates import render_template
from app.db.models import FreightRule, Item, PricingRule, Tenant, TenantItem, User
from app.middleware.host_routing import HostContext
from app.routers.auth import authenticate_user, register_tenant_and_user

router = APIRouter()


def require_public_host(request: Request):
    """Dependency to ensure request is on public host."""
    if request.state.host_context != HostContext.PUBLIC:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This route is only available on the public site",
        )


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request, _=Depends(require_public_host)):
    """Landing page with PT-BR copy and warnings."""
    return HTMLResponse(content=render_template("public/landing.html", {}))


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, _=Depends(require_public_host)):
    """Registration page."""
    return HTMLResponse(content=render_template("public/register.html", {}))


@router.post("/register", response_class=HTMLResponse)
async def register(
    request: Request,
    store_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Annotated[Session, Depends(get_db)] = None,
    _=Depends(require_public_host),
):
    """Handle registration."""
    try:
        tenant, user = register_tenant_and_user(db, store_name, email, password)

        # Create session with CSRF token
        session_id, csrf_token = create_session(user.id)

        # Redirect to onboarding
        response = RedirectResponse(
            url="/onboarding/step/1",
            status_code=status.HTTP_302_FOUND,
        )
        response.set_cookie(
            key="session_id",
            value=session_id,
            domain=".orcazap.com",  # Cross-subdomain
            secure=True,  # HTTPS only
            httponly=True,
            samesite="lax",
            max_age=86400 * 7,  # 7 days
        )
        # Set CSRF token cookie
        response.set_cookie(
            key="csrf_token",
            value=csrf_token,
            domain=".orcazap.com",
            httponly=False,  # Needs to be accessible to JavaScript for HTMX
            secure=True,
            samesite="lax",
            max_age=86400 * 7,  # 7 days
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        return HTMLResponse(
            content=render_template("public/register.html", {"error": str(e)}),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    tenant: Optional[str] = Query(None),
    next_url: Optional[str] = Query(None, alias="next"),
    db: Annotated[Session, Depends(get_db)] = None,
    _=Depends(require_public_host),
):
    """Login page."""
    # Check if user is already logged in
    try:
        user = await get_current_user(request, db)
        # User is logged in, redirect to tenant dashboard
        if user:
            tenant_obj = db.query(Tenant).filter_by(id=user.tenant_id).first()
            if tenant_obj and tenant_obj.slug:
                return RedirectResponse(
                    url=f"https://{tenant_obj.slug}.orcazap.com/",
                    status_code=status.HTTP_302_FOUND,
                )
    except HTTPException:
        pass  # Not logged in, show login page

    return HTMLResponse(content=render_template("public/login.html", {}))


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    tenant: Optional[str] = Query(None),
    next_url: Optional[str] = Query(None, alias="next"),
    db: Annotated[Session, Depends(get_db)] = None,
    _=Depends(require_public_host),
):
    """Handle login."""
    # Find user by email (globally, for simplicity)
    user = db.query(User).filter_by(email=email).first()
    if not user:
        return HTMLResponse(
            content=render_template("public/login.html", {"error": "Email ou senha inválidos"}),
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # Authenticate
    authenticated_user = authenticate_user(db, email, password, user.tenant_id)
    if not authenticated_user:
        return HTMLResponse(
            content=render_template("public/login.html", {"error": "Email ou senha inválidos"}),
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # Create session with CSRF token
    session_id, csrf_token = create_session(authenticated_user.id)

    # Get tenant for redirect
    tenant_obj = db.query(Tenant).filter_by(id=authenticated_user.tenant_id).first()
    if not tenant_obj or not tenant_obj.slug:
        return HTMLResponse(
            content=render_template("public/login.html", {"error": "Tenant não encontrado"}),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Redirect to tenant dashboard
    redirect_url = f"https://{tenant_obj.slug}.orcazap.com/"
    if next_url:
        redirect_url += next_url.lstrip("/")

    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="session_id",
        value=session_id,
        domain=".orcazap.com",  # Cross-subdomain
        secure=True,  # HTTPS only
        httponly=True,
        samesite="lax",
        max_age=86400 * 7,  # 7 days
    )
    # Set CSRF token cookie
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        domain=".orcazap.com",
        httponly=False,  # Needs to be accessible to JavaScript for HTMX
        secure=True,
        samesite="lax",
        max_age=86400 * 7,  # 7 days
    )
    return response


@router.post("/logout")
async def logout(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    _=Depends(require_public_host),
):
    """Handle logout."""
    session_id = request.cookies.get("session_id")
    if session_id:
        delete_session(session_id)

    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="session_id", domain=".orcazap.com")
    return response


@router.get("/onboarding", response_class=HTMLResponse)
async def onboarding_index(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)] = None,
    _=Depends(require_public_host),
):
    """Onboarding wizard entry - redirect to current step."""
    tenant = db.query(Tenant).filter_by(id=user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    step = tenant.onboarding_step or 1
    return RedirectResponse(
        url=f"/onboarding/step/{step}",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/onboarding/step/{step}", response_class=HTMLResponse)
async def onboarding_step_get(
    request: Request,
    step: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)] = None,
    _=Depends(require_public_host),
):
    """Render onboarding step form."""
    if step < 1 or step > 5:
        raise HTTPException(status_code=400, detail="Invalid step number")

    tenant = db.query(Tenant).filter_by(id=user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Render step template
    context = {}
    return HTMLResponse(content=render_onboarding_step(step, context))


@router.post("/onboarding/step/{step}")
async def onboarding_step_post(
    request: Request,
    step: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)] = None,
    _=Depends(require_public_host),
):
    """Save onboarding step data."""
    if step < 1 or step > 5:
        raise HTTPException(status_code=400, detail="Invalid step number")

    tenant = db.query(Tenant).filter_by(id=user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    form_data = await request.form()

    try:
        if step == 1:
            # Store info - just update tenant name if provided
            store_name = form_data.get("store_name")
            if store_name:
                tenant.name = store_name
            # Other fields can be stored in metadata or separate table if needed

        elif step == 2:
            # Freight rules
            i = 0
            while f"base_freight_{i}" in form_data:
                bairro = form_data.get(f"bairro_{i}") or None
                cep_start = form_data.get(f"cep_start_{i}") or None
                cep_end = form_data.get(f"cep_end_{i}") or None
                base_freight = Decimal(form_data.get(f"base_freight_{i}"))
                per_kg = form_data.get(f"per_kg_{i}")
                per_kg_additional = Decimal(per_kg) if per_kg else None

                freight_rule = FreightRule(
                    tenant_id=tenant.id,
                    bairro=bairro,
                    cep_range_start=cep_start,
                    cep_range_end=cep_end,
                    base_freight=base_freight,
                    per_kg_additional=per_kg_additional,
                )
                db.add(freight_rule)
                i += 1

        elif step == 3:
            # Pricing rules
            pix_discount = Decimal(form_data.get("pix_discount_pct"))
            margin_min = Decimal(form_data.get("margin_min_pct"))
            approval_total = form_data.get("approval_threshold_total")
            approval_margin = form_data.get("approval_threshold_margin")

            pricing_rule = PricingRule(
                tenant_id=tenant.id,
                pix_discount_pct=pix_discount,
                margin_min_pct=margin_min,
                approval_threshold_total=Decimal(approval_total) if approval_total else None,
                approval_threshold_margin=Decimal(approval_margin) if approval_margin else None,
            )
            db.add(pricing_rule)

        elif step == 4:
            # Items - handle CSV or manual input
            items_text = form_data.get("items_manual", "")
            csv_file = form_data.get("csv_file")

            items_to_process = []
            if csv_file and hasattr(csv_file, "file"):
                # Process CSV file
                import csv
                import io

                content = await csv_file.read()
                reader = csv.reader(io.StringIO(content.decode("utf-8")))
                for row in reader:
                    if len(row) >= 4:
                        items_to_process.append(row)
            elif items_text:
                # Process manual input
                for line in items_text.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 4:
                        items_to_process.append(parts)

            # Create items and tenant_items
            for item_data in items_to_process:
                sku, name, unit, price_str = item_data[:4]
                try:
                    price = Decimal(price_str)
                    # Find or create item
                    item = db.query(Item).filter_by(sku=sku).first()
                    if not item:
                        item = Item(sku=sku, name=name, unit=unit)
                        db.add(item)
                        db.flush()

                    # Create tenant_item
                    tenant_item = TenantItem(
                        tenant_id=tenant.id,
                        item_id=item.id,
                        price_base=price,
                        is_active=True,
                    )
                    db.add(tenant_item)
                except (ValueError, IndexError):
                    continue  # Skip invalid rows

        elif step == 5:
            # WhatsApp connection - just mark as complete
            # Actual connection will be done in tenant dashboard
            pass

        # Update onboarding step
        tenant.onboarding_step = step + 1 if step < 5 else None
        if step == 5:
            from datetime import datetime, timezone

            tenant.onboarding_completed_at = datetime.now(timezone.utc)

        db.commit()

    except Exception as e:
        db.rollback()
        return HTMLResponse(
            content=render_onboarding_step(step, {"error": str(e)}),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Redirect to next step or dashboard
    if step < 5:
        return RedirectResponse(
            url=f"/onboarding/step/{step + 1}",
            status_code=status.HTTP_302_FOUND,
        )
    else:
        # Onboarding complete, redirect to tenant dashboard
        return RedirectResponse(
            url=f"https://{tenant.slug}.orcazap.com/",
            status_code=status.HTTP_302_FOUND,
        )
