"""Tenant router for {slug}.orcazap.com."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from fastapi import Form
from uuid import UUID

from decimal import Decimal

from app.core.dependencies import get_current_user, get_db
from app.core.csrf import require_csrf_token
from app.core.stripe import is_subscription_active
from app.db.models import (
    Approval,
    ApprovalStatus,
    Channel,
    Contact,
    Conversation,
    ConversationState,
    FreightRule,
    Item,
    Message,
    MessageDirection,
    MessageTemplate,
    PricingRule,
    Quote,
    QuoteStatus,
    Tenant,
    TenantItem,
    User,
)
from app.domain.metrics import get_tenant_metrics
from app.middleware.host_routing import HostContext
from sqlalchemy import desc, or_

router = APIRouter()


def require_tenant_host(request: Request):
    """Dependency to ensure request is on tenant host with valid tenant."""
    if request.state.host_context != HostContext.TENANT:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This route is only available on tenant subdomains",
        )
    if not request.state.tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    _=Depends(require_tenant_host),
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Tenant dashboard with metrics."""
    tenant = request.state.tenant
    
    # Check authentication - if not authenticated, redirect to login
    try:
        user = get_current_user(request, db)
        user_email = user.email
    except HTTPException:
        # Not authenticated, redirect to public login
        slug = tenant.slug
        return RedirectResponse(
            url=f"https://orcazap.com/login?tenant={slug}&next=/",
            status_code=status.HTTP_302_FOUND,
        )

    # Get metrics
    metrics = get_tenant_metrics(db, tenant.id)

    # Get pending approvals count
    pending_approvals = (
        db.query(Approval)
        .filter_by(tenant_id=tenant.id, status=ApprovalStatus.PENDING)
        .count()
    )

    # Get WhatsApp channel status
    channel = db.query(Channel).filter_by(tenant_id=tenant.id, is_active=True).first()
    whatsapp_status = {
        "connected": False,
        "is_active": False,
        "last_message": None,
        "last_message_time": None,
    }
    
    if channel:
        whatsapp_status["connected"] = True
        whatsapp_status["is_active"] = channel.is_active
        
        # Get last message (inbound or outbound)
        last_message = (
            db.query(Message)
            .filter_by(tenant_id=tenant.id)
            .order_by(desc(Message.created_at))
            .first()
        )
        
        if last_message:
            whatsapp_status["last_message"] = (
                last_message.text_content[:100] + "..." 
                if last_message.text_content and len(last_message.text_content) > 100 
                else (last_message.text_content or "Mensagem sem texto")
            )
            whatsapp_status["last_message_time"] = last_message.created_at
            whatsapp_status["last_message_direction"] = last_message.direction.value

    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Dashboard - {tenant.name}</title>
            <meta charset="utf-8">
            <script src="https://unpkg.com/htmx.org@1.9.10"></script>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                h1 {{ color: #007bff; }}
                .metrics {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 20px;
                    margin: 20px 0;
                }}
                .metric-card {{
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 8px;
                    border: 1px solid #dee2e6;
                }}
                .metric-value {{
                    font-size: 2em;
                    font-weight: bold;
                    color: #007bff;
                }}
                .metric-label {{
                    color: #6c757d;
                    margin-top: 5px;
                }}
                nav {{
                    margin: 20px 0;
                    padding: 10px 0;
                    border-bottom: 1px solid #dee2e6;
                }}
                nav a {{
                    margin-right: 20px;
                    color: #007bff;
                    text-decoration: none;
                }}
                nav a:hover {{
                    text-decoration: underline;
                }}
                .whatsapp-status {{
                    background: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 8px;
                    padding: 20px;
                    margin: 20px 0;
                }}
                .status-indicator {{
                    display: inline-block;
                    width: 12px;
                    height: 12px;
                    border-radius: 50%;
                    margin-right: 8px;
                }}
                .status-active {{
                    background: #28a745;
                }}
                .status-inactive {{
                    background: #dc3545;
                }}
                .status-disconnected {{
                    background: #6c757d;
                }}
                .last-message {{
                    margin-top: 10px;
                    padding-top: 10px;
                    border-top: 1px solid #dee2e6;
                    font-size: 0.9em;
                    color: #6c757d;
                }}
            </style>
        </head>
        <body>
            <h1>Dashboard - {tenant.name}</h1>
            <p>Logado como: {user_email}</p>
            
            <nav>
                <a href="/">Dashboard</a>
                <a href="/approvals">Aprovações</a>
                <a href="/prices">Preços</a>
                <a href="/freight">Frete</a>
                <a href="/rules">Regras</a>
                <a href="/conversations">Conversas</a>
                <a href="/quotes">Orçamentos</a>
                <a href="/templates">Templates</a>
            </nav>

            <div class="whatsapp-status">
                <h3>Status WhatsApp</h3>
                {f'''
                <p>
                    <span class="status-indicator {'status-active' if whatsapp_status['is_active'] else 'status-inactive'}"></span>
                    <strong>{'Conectado e Ativo' if whatsapp_status['is_active'] else 'Conectado mas Inativo'}</strong>
                </p>
                ''' if whatsapp_status['connected'] else '''
                <p>
                    <span class="status-indicator status-disconnected"></span>
                    <strong>Não Conectado</strong>
                </p>
                <p style="color: #856404; margin-top: 10px;">
                    Configure seu número WhatsApp no onboarding para começar a receber mensagens.
                </p>
                '''}
                {f'''
                <div class="last-message">
                    <strong>Última mensagem ({'Recebida' if whatsapp_status.get('last_message_direction') == 'inbound' else 'Enviada'}):</strong><br>
                    {whatsapp_status['last_message']}<br>
                    <small>{whatsapp_status['last_message_time'].strftime('%d/%m/%Y %H:%M') if whatsapp_status['last_message_time'] else ''}</small>
                </div>
                ''' if whatsapp_status.get('last_message') else ''}
            </div>

            <div class="metrics">
                <div class="metric-card">
                    <div class="metric-value">{metrics['quotes_today']}</div>
                    <div class="metric-label">Orçamentos Hoje</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{metrics['quotes_7d']}</div>
                    <div class="metric-label">Orçamentos (7 dias)</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{metrics['quotes_30d']}</div>
                    <div class="metric-label">Orçamentos (30 dias)</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{metrics['approvals_pending']}</div>
                    <div class="metric-label">Aprovações Pendentes</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{metrics['messages_processed']}</div>
                    <div class="metric-label">Mensagens Processadas</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{metrics['conversions_won']}</div>
                    <div class="metric-label">Conversões (Ganhos)</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{metrics['conversions_lost']}</div>
                    <div class="metric-label">Conversões (Perdidos)</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{metrics['conversion_rate']}%</div>
                    <div class="metric-label">Taxa de Conversão</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{metrics['ai_usage_count']}</div>
                    <div class="metric-label">Uso de IA</div>
                </div>
            </div>
            
            {f'<div style="background: #fff3cd; border: 1px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 5px;"><strong>⚠️ Assinatura Inativa:</strong> Ative sua assinatura para usar o WhatsApp. <a href="https://orcazap.com/pricing">Ver planos</a></div>' if not is_subscription_active(tenant) else ''}
        </body>
        </html>
        """
    )


@router.get("/approvals", response_class=HTMLResponse)
async def approvals_list(
    request: Request,
    _=Depends(require_tenant_host),
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Approvals queue (HTMX)."""
    tenant = request.state.tenant
    
    # Check authentication
    try:
        user = get_current_user(request, db)
    except HTTPException:
        slug = tenant.slug
        return RedirectResponse(
            url=f"https://orcazap.com/login?tenant={slug}&next=/approvals",
            status_code=status.HTTP_302_FOUND,
        )

    # Get pending approvals
    approvals = (
        db.query(Approval)
        .filter_by(tenant_id=tenant.id, status=ApprovalStatus.PENDING)
        .all()
    )

    # Simple placeholder for now - full HTMX implementation in Phase 2 completion
    approvals_html = ""
    for approval in approvals:
        approvals_html += f"<p>Aprovação ID: {approval.id} - Status: {approval.status}</p>"

    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Aprovações - {tenant.name}</title>
            <meta charset="utf-8">
            <script src="https://unpkg.com/htmx.org@1.9.10"></script>
        </head>
        <body>
            <h1>Aprovações Pendentes</h1>
            {approvals_html if approvals_html else "<p>Nenhuma aprovação pendente.</p>"}
            <p><a href="/">Voltar ao Dashboard</a></p>
        </body>
        </html>
        """
    )


@router.get("/templates", response_class=HTMLResponse)
async def templates_list(
    request: Request,
    _=Depends(require_tenant_host),
    db: Annotated[Session, Depends(get_db)] = None,
):
    """List and edit message templates."""
    tenant = request.state.tenant
    
    # Check authentication
    try:
        user = get_current_user(request, db)
    except HTTPException:
        slug = tenant.slug
        return RedirectResponse(
            url=f"https://orcazap.com/login?tenant={slug}&next=/templates",
            status_code=status.HTTP_302_FOUND,
        )

    # Get all templates for tenant
    templates = (
        db.query(MessageTemplate)
        .filter_by(tenant_id=tenant.id)
        .order_by(MessageTemplate.template_type, MessageTemplate.name)
        .all()
    )

    # Group by type
    templates_by_type = {}
    for template in templates:
        if template.template_type not in templates_by_type:
            templates_by_type[template.template_type] = []
        templates_by_type[template.template_type].append(template)

    # Template types with descriptions
    template_types = {
        "data_capture": "Prompt de Captura de Dados",
        "quote": "Mensagem de Orçamento",
        "approval": "Mensagem de Aprovação Pendente",
    }

    templates_html = ""
    for template_type, description in template_types.items():
        type_templates = templates_by_type.get(template_type, [])
        templates_html += f"""
        <div style="margin: 20px 0; padding: 15px; border: 1px solid #dee2e6; border-radius: 8px;">
            <h3>{description} ({template_type})</h3>
        """
        
        if type_templates:
            for template in type_templates:
                templates_html += f"""
                <div style="margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 4px;">
                    <strong>{template.name or 'Padrão'}</strong> {'(Ativo)' if template.is_active else '(Inativo)'}
                    <a href="/templates/edit/{template.id}" style="margin-left: 10px; color: #007bff;">Editar</a>
                </div>
                """
        else:
            templates_html += f"""
            <p style="color: #6c757d;">Nenhum template configurado. <a href="/templates/new?type={template_type}">Criar template</a></p>
            """
        
        templates_html += "</div>"

    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Templates - {tenant.name}</title>
            <meta charset="utf-8">
            <script src="https://unpkg.com/htmx.org@1.9.10"></script>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                nav {{
                    margin: 20px 0;
                    padding: 10px 0;
                    border-bottom: 1px solid #dee2e6;
                }}
                nav a {{
                    margin-right: 20px;
                    color: #007bff;
                    text-decoration: none;
                }}
                textarea {{
                    width: 100%;
                    min-height: 200px;
                    padding: 10px;
                    font-family: monospace;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                }}
                button {{
                    padding: 10px 20px;
                    background: #007bff;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    margin-top: 10px;
                }}
            </style>
        </head>
        <body>
            <h1>Templates de Mensagens</h1>
            <nav>
                <a href="/">Dashboard</a>
                <a href="/templates">Templates</a>
            </nav>
            
            {templates_html}
            
            <p><a href="/">Voltar ao Dashboard</a></p>
        </body>
        </html>
        """
    )


@router.get("/templates/new", response_class=HTMLResponse)
@router.get("/templates/edit/{template_id}", response_class=HTMLResponse)
async def template_edit(
    request: Request,
    template_id: UUID | None = None,
    template_type: str | None = None,
    _=Depends(require_tenant_host),
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Edit or create a message template."""
    tenant = request.state.tenant
    
    # Check authentication
    try:
        user = get_current_user(request, db)
    except HTTPException:
        slug = tenant.slug
        return RedirectResponse(
            url=f"https://orcazap.com/login?tenant={slug}&next=/templates",
            status_code=status.HTTP_302_FOUND,
        )

    template = None
    if template_id:
        template = db.query(MessageTemplate).filter_by(id=template_id, tenant_id=tenant.id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
    
    # Get template_type from query param or existing template
    if not template_type:
        template_type = request.query_params.get("type")
    if not template_type and template:
        template_type = template.template_type
    
    if not template_type:
        raise HTTPException(status_code=400, detail="Template type is required")

    template_types = {
        "data_capture": "Prompt de Captura de Dados",
        "quote": "Mensagem de Orçamento",
        "approval": "Mensagem de Aprovação Pendente",
    }

    # Default templates
    default_templates = {
        "data_capture": """Olá{%, if contact_name %}, {{ contact_name }}{% endif %}! 👋

Para gerar seu orçamento, preciso das seguintes informações:

📍 *Localização:* [CEP ou bairro]
💳 *Forma de pagamento:* [PIX / Cartão / Boleto]
📅 *Dia de entrega:* [Data ou "o quanto antes"]
📦 *Itens:* [Lista de produtos com quantidades]

Exemplo:
📍 CEP: 01310-100 ou Bairro: Centro
💳 PIX
📅 Amanhã
📦
- Cimento 50kg: 10 sacos
- Areia média: 2m³
- Tijolo comum: 500 unidades""",
        "quote": """✅ *Orçamento Gerado*

*Itens:*
{% for item in items %}
• {{ item.name }} ({{ item.quantity }} {{ item.unit }}): R$ {{ "%.2f"|format(item.total) }}
{% endfor %}

*Subtotal:* R$ {{ "%.2f"|format(subtotal) }}
*Frete:* R$ {{ "%.2f"|format(freight) }}
{% if discount_pct > 0 %}
*Desconto {{ "PIX" if payment_method.upper() == "PIX" else "" }} ({{ "%.0f"|format(discount_pct*100) }}%):* -R$ {{ "%.2f"|format(discount_amount) }}
{% endif %}
━━━━━━━━━━━━━━━━
*Total:* R$ {{ "%.2f"|format(total) }}

💳 *Forma de pagamento:* {{ payment_method }}
📅 *Entrega:* {{ delivery_day }}

⏰ *Válido até:* {{ valid_until.strftime("%d/%m/%Y às %H:%M") }}

Para agendar a entrega, responda:
✅ *Confirmar* ou *Sim*

Ou envie sua dúvida que te ajudo! 😊""",
        "approval": """Olá! 👋

Recebi sua solicitação. Para garantir o melhor atendimento, nossa equipe está analisando seu pedido e entrará em contato em breve.

Você receberá uma resposta em até 2 horas úteis.

Obrigado pela compreensão! 🙏""",
    }

    content = template.content if template else default_templates.get(template_type, "")
    signature = template.signature if template else ""
    quote_type_value = template.quote_type if template else ""
    # Escape HTML in content for textarea
    content_escaped = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    signature_escaped = signature.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    edit_or_create = "Editar" if template else "Criar"
    template_id_value = str(template.id) if template else ""
    template_name_value = template.name if template else ""
    checked_attr = "checked" if not template or template.is_active else ""
    
    # Show quote_type field only for quote templates
    quote_type_field = ""
    if template_type == "quote":
        quote_type_field = f"""
                <label>
                    <strong>Tipo de Orçamento (opcional):</strong>
                    <select name="quote_type">
                        <option value="">Padrão</option>
                        <option value="residencial" {'selected' if quote_type_value == 'residencial' else ''}>Residencial</option>
                        <option value="comercial" {'selected' if quote_type_value == 'comercial' else ''}>Comercial</option>
                    </select>
                </label>
        """

    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{edit_or_create} Template - {tenant.name}</title>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 900px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                form {{
                    display: flex;
                    flex-direction: column;
                    gap: 15px;
                }}
                input, textarea {{
                    padding: 10px;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                    font-family: Arial, sans-serif;
                }}
                textarea {{
                    min-height: 300px;
                    font-family: monospace;
                }}
                button {{
                    padding: 12px 24px;
                    background: #007bff;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                }}
                .info {{
                    background: #e7f3ff;
                    padding: 15px;
                    border-radius: 4px;
                    margin-bottom: 20px;
                }}
            </style>
        </head>
        <body>
            <h1>{edit_or_create} Template</h1>
            <p><a href="/templates">← Voltar para Templates</a></p>
            
            <div class="info">
                <strong>Tipo:</strong> {template_types.get(template_type, template_type)}<br>
                <strong>Variáveis disponíveis:</strong> contact_name, items, subtotal, freight, discount_pct, discount_amount, total, payment_method, delivery_day, valid_until
            </div>
            
            <form method="POST" action="/templates/save">
                <input type="hidden" name="template_id" value="{template_id_value}">
                <input type="hidden" name="template_type" value="{template_type}">
                
                <label>
                    <strong>Nome do Template (opcional):</strong>
                    <input type="text" name="name" value="{template_name_value}" placeholder="Deixe vazio para template padrão">
                </label>
                
                <label>
                    <strong>Conteúdo do Template (Jinja2):</strong>
                    <textarea name="content" required>{content_escaped}</textarea>
                </label>
                
                {quote_type_field}
                
                <label>
                    <strong>Assinatura Automática (opcional, Jinja2):</strong>
                    <textarea name="signature" placeholder="Ex: Equipe {{ tenant_name }}">{signature_escaped}</textarea>
                    <small>Será adicionada automaticamente ao final da mensagem</small>
                </label>
                
                <label>
                    <input type="checkbox" name="is_active" {checked_attr}>
                    Template ativo
                </label>
                
                <button type="submit">Salvar Template</button>
            </form>
        </body>
        </html>
        """
    )


@router.post("/templates/save", response_class=HTMLResponse)
async def template_save(
    request: Request,
    template_id: str = Form(""),
    template_type: str = Form(...),
    name: str = Form(""),
    content: str = Form(...),
    quote_type: str = Form(""),
    signature: str = Form(""),
    is_active: bool = Form(False),
    _=Depends(require_tenant_host),
    db: Annotated[Session, Depends(get_db)] = None,
    __: None = Depends(require_csrf_token),
):
    """Save a message template."""
    tenant = request.state.tenant
    
    # Check authentication
    try:
        user = get_current_user(request, db)
    except HTTPException:
        slug = tenant.slug
        return RedirectResponse(
            url=f"https://orcazap.com/login?tenant={slug}&next=/templates",
            status_code=status.HTTP_302_FOUND,
        )

    # Import validation functions
    from app.core.template_validation import sanitize_template_content, validate_template_content
    
    # Sanitize and validate template content
    content = sanitize_template_content(content)
    is_valid, error_msg = validate_template_content(content)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid template content: {error_msg}",
        )
    
    # Sanitize signature if provided
    if signature:
        signature = sanitize_template_content(signature)
        is_valid, error_msg = validate_template_content(signature)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid signature template: {error_msg}",
            )
    
    # Normalize name (empty string becomes None)
    template_name = name.strip() if name.strip() else None

    # Normalize quote_type (empty string becomes None)
    quote_type_value = quote_type.strip() if quote_type.strip() else None
    signature_value = signature.strip() if signature.strip() else None

    if template_id:
        # Update existing
        template = db.query(MessageTemplate).filter_by(id=UUID(template_id), tenant_id=tenant.id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        template.content = content
        template.name = template_name
        template.is_active = is_active
        template.quote_type = quote_type_value
        template.signature = signature_value
        template.version += 1
    else:
        # Create new
        template = MessageTemplate(
            tenant_id=tenant.id,
            template_type=template_type,
            name=template_name,
            content=content,
            quote_type=quote_type_value,
            signature=signature_value,
            is_active=is_active,
            version=1,
        )
        db.add(template)
    
    db.commit()
    
    return RedirectResponse(
        url="/templates",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/prices", response_class=HTMLResponse)
async def prices_list(
    request: Request,
    _=Depends(require_tenant_host),
    db: Annotated[Session, Depends(get_db)] = None,
):
    """List and manage items and prices."""
    tenant = request.state.tenant
    
    # Check authentication
    try:
        user = get_current_user(request, db)
    except HTTPException:
        slug = tenant.slug
        return RedirectResponse(
            url=f"https://orcazap.com/login?tenant={slug}&next=/prices",
            status_code=status.HTTP_302_FOUND,
        )

    # Get search query
    search = request.query_params.get("search", "")

    # Get tenant items with item details
    query = (
        db.query(TenantItem, Item)
        .join(Item, TenantItem.item_id == Item.id)
        .filter_by(tenant_id=tenant.id)
    )
    
    if search:
        query = query.filter(
            or_(
                Item.sku.ilike(f"%{search}%"),
                Item.name.ilike(f"%{search}%"),
            )
        )
    
    tenant_items = query.order_by(Item.name).all()

    items_html = ""
    for tenant_item, item in tenant_items:
        items_html += f"""
        <tr>
            <td>{item.sku}</td>
            <td>{item.name}</td>
            <td>{item.unit}</td>
            <td>R$ {float(tenant_item.price_base):,.2f}</td>
            <td>{'Ativo' if tenant_item.is_active else 'Inativo'}</td>
            <td>
                <a href="/prices/edit/{tenant_item.id}">Editar</a>
            </td>
        </tr>
        """

    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Preços - {tenant.name}</title>
            <meta charset="utf-8">
            <script src="https://unpkg.com/htmx.org@1.9.10"></script>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }}
                th, td {{
                    padding: 10px;
                    text-align: left;
                    border: 1px solid #dee2e6;
                }}
                th {{
                    background: #f8f9fa;
                }}
                nav {{
                    margin: 20px 0;
                    padding: 10px 0;
                    border-bottom: 1px solid #dee2e6;
                }}
                nav a {{
                    margin-right: 20px;
                    color: #007bff;
                    text-decoration: none;
                }}
                input, button {{
                    padding: 8px;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                }}
                button {{
                    background: #007bff;
                    color: white;
                    cursor: pointer;
                }}
            </style>
        </head>
        <body>
            <h1>Preços e Itens</h1>
            <nav>
                <a href="/">Dashboard</a>
                <a href="/prices">Preços</a>
            </nav>
            
            <div style="margin: 20px 0;">
                <form method="GET" style="display: flex; gap: 10px;">
                    <input type="text" name="search" placeholder="Buscar por SKU ou nome..." value="{search}">
                    <button type="submit">Buscar</button>
                </form>
                <a href="/prices/new" style="display: inline-block; margin-top: 10px; padding: 10px 20px; background: #28a745; color: white; text-decoration: none; border-radius: 4px;">+ Novo Item</a>
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>SKU</th>
                        <th>Nome</th>
                        <th>Unidade</th>
                        <th>Preço Base</th>
                        <th>Status</th>
                        <th>Ações</th>
                    </tr>
                </thead>
                <tbody>
                    {items_html if items_html else "<tr><td colspan='6'>Nenhum item encontrado. <a href='/prices/new'>Criar primeiro item</a></td></tr>"}
                </tbody>
            </table>
            
            <p><a href="/">Voltar ao Dashboard</a></p>
        </body>
        </html>
        """
    )


@router.get("/prices/new", response_class=HTMLResponse)
@router.get("/prices/edit/{tenant_item_id}", response_class=HTMLResponse)
async def price_edit(
    request: Request,
    tenant_item_id: UUID | None = None,
    _=Depends(require_tenant_host),
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Create or edit an item and price."""
    tenant = request.state.tenant
    
    # Check authentication
    try:
        user = get_current_user(request, db)
    except HTTPException:
        slug = tenant.slug
        return RedirectResponse(
            url=f"https://orcazap.com/login?tenant={slug}&next=/prices",
            status_code=status.HTTP_302_FOUND,
        )

    tenant_item = None
    item = None
    if tenant_item_id:
        tenant_item = db.query(TenantItem).filter_by(id=tenant_item_id, tenant_id=tenant.id).first()
        if not tenant_item:
            raise HTTPException(status_code=404, detail="Item not found")
        item = db.query(Item).filter_by(id=tenant_item.item_id).first()

    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{'Editar' if tenant_item else 'Novo'} Item - {tenant.name}</title>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                form {{
                    display: flex;
                    flex-direction: column;
                    gap: 15px;
                }}
                input, select {{
                    padding: 10px;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                }}
                button {{
                    padding: 12px 24px;
                    background: #007bff;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                }}
            </style>
        </head>
        <body>
            <h1>{'Editar' if tenant_item else 'Novo'} Item</h1>
            <p><a href="/prices">← Voltar para Preços</a></p>
            
            <form method="POST" action="/prices/save">
                <input type="hidden" name="tenant_item_id" value="{tenant_item.id if tenant_item else ''}">
                
                <label>
                    <strong>SKU:</strong>
                    <input type="text" name="sku" value="{item.sku if item else ''}" required {'readonly' if tenant_item else ''}>
                </label>
                
                <label>
                    <strong>Nome:</strong>
                    <input type="text" name="name" value="{item.name if item else ''}" required>
                </label>
                
                <label>
                    <strong>Unidade:</strong>
                    <input type="text" name="unit" value="{item.unit if item else ''}" placeholder="kg, m², un, etc." required>
                </label>
                
                <label>
                    <strong>Preço Base (R$):</strong>
                    <input type="number" name="price_base" step="0.01" min="0" value="{float(tenant_item.price_base) if tenant_item else ''}" required>
                </label>
                
                <label>
                    <input type="checkbox" name="is_active" {'checked' if not tenant_item or tenant_item.is_active else ''}>
                    Item ativo
                </label>
                
                <button type="submit">Salvar</button>
            </form>
        </body>
        </html>
        """
    )


@router.post("/prices/save", response_class=HTMLResponse)
async def price_save(
    request: Request,
    tenant_item_id: str = Form(""),
    _csrf: None = Depends(require_csrf_token),
    sku: str = Form(...),
    name: str = Form(...),
    unit: str = Form(...),
    price_base: str = Form(...),
    is_active: bool = Form(False),
    _=Depends(require_tenant_host),
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Save an item and price."""
    tenant = request.state.tenant
    
    # Check authentication
    try:
        user = get_current_user(request, db)
    except HTTPException:
        slug = tenant.slug
        return RedirectResponse(
            url=f"https://orcazap.com/login?tenant={slug}&next=/prices",
            status_code=status.HTTP_302_FOUND,
        )

    try:
        price = Decimal(price_base)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Preço inválido")

    if tenant_item_id:
        # Update existing
        tenant_item = db.query(TenantItem).filter_by(id=UUID(tenant_item_id), tenant_id=tenant.id).first()
        if not tenant_item:
            raise HTTPException(status_code=404, detail="Item not found")
        
        item = db.query(Item).filter_by(id=tenant_item.item_id).first()
        item.name = name
        item.unit = unit
        tenant_item.price_base = price
        tenant_item.is_active = is_active
    else:
        # Create new
        # Check if item with SKU exists
        item = db.query(Item).filter_by(sku=sku).first()
        if not item:
            item = Item(sku=sku, name=name, unit=unit)
            db.add(item)
            db.flush()
        
        # Check if tenant_item already exists
        existing = db.query(TenantItem).filter_by(tenant_id=tenant.id, item_id=item.id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Item já existe para este tenant")
        
        tenant_item = TenantItem(
            tenant_id=tenant.id,
            item_id=item.id,
            price_base=price,
            is_active=is_active,
        )
        db.add(tenant_item)
    
    db.commit()
    
    return RedirectResponse(
        url="/prices",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/freight", response_class=HTMLResponse)
async def freight_list(
    request: Request,
    _=Depends(require_tenant_host),
    db: Annotated[Session, Depends(get_db)] = None,
):
    """List and manage freight rules."""
    tenant = request.state.tenant
    
    # Check authentication
    try:
        user = get_current_user(request, db)
    except HTTPException:
        slug = tenant.slug
        return RedirectResponse(
            url=f"https://orcazap.com/login?tenant={slug}&next=/freight",
            status_code=status.HTTP_302_FOUND,
        )

    freight_rules = db.query(FreightRule).filter_by(tenant_id=tenant.id).order_by(FreightRule.created_at).all()

    rules_html = ""
    for rule in freight_rules:
        location = rule.bairro or f"CEP {rule.cep_range_start} - {rule.cep_range_end}"
        per_kg = f"R$ {float(rule.per_kg_additional):,.2f}/kg" if rule.per_kg_additional else "N/A"
        rules_html += f"""
        <tr>
            <td>{location}</td>
            <td>R$ {float(rule.base_freight):,.2f}</td>
            <td>{per_kg}</td>
            <td>
                <a href="/freight/edit/{rule.id}">Editar</a>
                <a href="/freight/delete/{rule.id}" onclick="return confirm('Tem certeza?')" style="color: #dc3545; margin-left: 10px;">Excluir</a>
            </td>
        </tr>
        """

    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Frete - {tenant.name}</title>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }}
                th, td {{
                    padding: 10px;
                    text-align: left;
                    border: 1px solid #dee2e6;
                }}
                th {{
                    background: #f8f9fa;
                }}
                nav a {{
                    margin-right: 20px;
                    color: #007bff;
                    text-decoration: none;
                }}
                button {{
                    padding: 10px 20px;
                    background: #28a745;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    margin-top: 10px;
                }}
            </style>
        </head>
        <body>
            <h1>Regras de Frete</h1>
            <nav>
                <a href="/">Dashboard</a>
                <a href="/freight">Frete</a>
            </nav>
            
            <a href="/freight/new"><button>+ Nova Regra de Frete</button></a>
            
            <table>
                <thead>
                    <tr>
                        <th>Localização</th>
                        <th>Frete Base</th>
                        <th>Por kg adicional</th>
                        <th>Ações</th>
                    </tr>
                </thead>
                <tbody>
                    {rules_html if rules_html else "<tr><td colspan='4'>Nenhuma regra de frete configurada. <a href='/freight/new'>Criar primeira regra</a></td></tr>"}
                </tbody>
            </table>
            
            <p><a href="/">Voltar ao Dashboard</a></p>
        </body>
        </html>
        """
    )


@router.get("/freight/new", response_class=HTMLResponse)
@router.get("/freight/edit/{rule_id}", response_class=HTMLResponse)
async def freight_edit(
    request: Request,
    rule_id: UUID | None = None,
    _=Depends(require_tenant_host),
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Create or edit a freight rule."""
    tenant = request.state.tenant
    
    # Check authentication
    try:
        user = get_current_user(request, db)
    except HTTPException:
        slug = tenant.slug
        return RedirectResponse(
            url=f"https://orcazap.com/login?tenant={slug}&next=/freight",
            status_code=status.HTTP_302_FOUND,
        )

    rule = None
    if rule_id:
        rule = db.query(FreightRule).filter_by(id=rule_id, tenant_id=tenant.id).first()
        if not rule:
            raise HTTPException(status_code=404, detail="Regra não encontrada")

    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{'Editar' if rule else 'Nova'} Regra de Frete - {tenant.name}</title>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                form {{
                    display: flex;
                    flex-direction: column;
                    gap: 15px;
                }}
                input {{
                    padding: 10px;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                }}
                button {{
                    padding: 12px 24px;
                    background: #007bff;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                }}
                .info {{
                    background: #e7f3ff;
                    padding: 15px;
                    border-radius: 4px;
                    margin-bottom: 20px;
                }}
            </style>
        </head>
        <body>
            <h1>{'Editar' if rule else 'Nova'} Regra de Frete</h1>
            <p><a href="/freight">← Voltar para Frete</a></p>
            
            <div class="info">
                <strong>Configure por Bairro ou por CEP:</strong><br>
                - Para bairro: preencha apenas o campo "Bairro"<br>
                - Para CEP: preencha "CEP Início" e "CEP Fim"
            </div>
            
            <form method="POST" action="/freight/save">
                <input type="hidden" name="rule_id" value="{rule.id if rule else ''}">
                
                <label>
                    <strong>Bairro (opcional):</strong>
                    <input type="text" name="bairro" value="{rule.bairro if rule else ''}" placeholder="Ex: Centro">
                </label>
                
                <label>
                    <strong>CEP Início (opcional):</strong>
                    <input type="text" name="cep_start" value="{rule.cep_range_start if rule else ''}" placeholder="Ex: 01310-100">
                </label>
                
                <label>
                    <strong>CEP Fim (opcional):</strong>
                    <input type="text" name="cep_end" value="{rule.cep_range_end if rule else ''}" placeholder="Ex: 01310-999">
                </label>
                
                <label>
                    <strong>Frete Base (R$):</strong>
                    <input type="number" name="base_freight" step="0.01" min="0" value="{float(rule.base_freight) if rule else ''}" required>
                </label>
                
                <label>
                    <strong>Por kg adicional (R$, opcional):</strong>
                    <input type="number" name="per_kg" step="0.01" min="0" value="{float(rule.per_kg_additional) if rule and rule.per_kg_additional else ''}" placeholder="Deixe vazio se não aplicar">
                </label>
                
                <button type="submit">Salvar</button>
            </form>
        </body>
        </html>
        """
    )


@router.post("/freight/save", response_class=HTMLResponse)
async def freight_save(
    request: Request,
    rule_id: str = Form(""),
    bairro: str = Form(""),
    cep_start: str = Form(""),
    cep_end: str = Form(""),
    base_freight: str = Form(...),
    per_kg: str = Form(""),
    _=Depends(require_tenant_host),
    db: Annotated[Session, Depends(get_db)] = None,
    __: None = Depends(require_csrf_token),
):
    """Save a freight rule."""
    tenant = request.state.tenant
    
    # Check authentication
    try:
        user = get_current_user(request, db)
    except HTTPException:
        slug = tenant.slug
        return RedirectResponse(
            url=f"https://orcazap.com/login?tenant={slug}&next=/freight",
            status_code=status.HTTP_302_FOUND,
        )

    # Validate: must have either bairro or CEP range
    bairro = bairro.strip() if bairro else None
    cep_start = cep_start.strip() if cep_start else None
    cep_end = cep_end.strip() if cep_end else None
    
    if not bairro and (not cep_start or not cep_end):
        raise HTTPException(status_code=400, detail="Deve preencher Bairro ou CEP Início/Fim")

    try:
        base = Decimal(base_freight)
        per_kg_additional = Decimal(per_kg) if per_kg.strip() else None
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Valores inválidos")

    if rule_id:
        # Update existing
        rule = db.query(FreightRule).filter_by(id=UUID(rule_id), tenant_id=tenant.id).first()
        if not rule:
            raise HTTPException(status_code=404, detail="Regra não encontrada")
        
        rule.bairro = bairro
        rule.cep_range_start = cep_start
        rule.cep_range_end = cep_end
        rule.base_freight = base
        rule.per_kg_additional = per_kg_additional
    else:
        # Create new
        rule = FreightRule(
            tenant_id=tenant.id,
            bairro=bairro,
            cep_range_start=cep_start,
            cep_range_end=cep_end,
            base_freight=base,
            per_kg_additional=per_kg_additional,
        )
        db.add(rule)
    
    db.commit()
    
    return RedirectResponse(
        url="/freight",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/freight/delete/{rule_id}", response_class=HTMLResponse)
async def freight_delete(
    request: Request,
    rule_id: UUID,
    _=Depends(require_tenant_host),
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Delete a freight rule."""
    tenant = request.state.tenant
    
    # Check authentication
    try:
        user = get_current_user(request, db)
    except HTTPException:
        slug = tenant.slug
        return RedirectResponse(
            url=f"https://orcazap.com/login?tenant={slug}&next=/freight",
            status_code=status.HTTP_302_FOUND,
        )

    rule = db.query(FreightRule).filter_by(id=rule_id, tenant_id=tenant.id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Regra não encontrada")
    
    db.delete(rule)
    db.commit()
    
    return RedirectResponse(
        url="/freight",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/rules", response_class=HTMLResponse)
async def rules_edit(
    request: Request,
    _=Depends(require_tenant_host),
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Edit pricing rules."""
    tenant = request.state.tenant
    
    # Check authentication
    try:
        user = get_current_user(request, db)
    except HTTPException:
        slug = tenant.slug
        return RedirectResponse(
            url=f"https://orcazap.com/login?tenant={slug}&next=/rules",
            status_code=status.HTTP_302_FOUND,
        )

    rule = db.query(PricingRule).filter_by(tenant_id=tenant.id).first()

    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Regras de Preço - {tenant.name}</title>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                form {{
                    display: flex;
                    flex-direction: column;
                    gap: 15px;
                }}
                input {{
                    padding: 10px;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                }}
                button {{
                    padding: 12px 24px;
                    background: #007bff;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                }}
                .info {{
                    background: #e7f3ff;
                    padding: 15px;
                    border-radius: 4px;
                    margin-bottom: 20px;
                }}
            </style>
        </head>
        <body>
            <h1>Regras de Preço</h1>
            <nav>
                <a href="/">Dashboard</a>
                <a href="/rules">Regras</a>
            </nav>
            
            <div class="info">
                <strong>Configure as regras de precificação:</strong><br>
                - Desconto PIX: porcentagem de desconto para pagamento via PIX<br>
                - Margem mínima: margem mínima aceita antes de requerer aprovação<br>
                - Limites de aprovação: valores que requerem aprovação manual
            </div>
            
            <form method="POST" action="/rules/save">
                <label>
                    <strong>Desconto PIX (%):</strong>
                    <input type="number" name="pix_discount_pct" step="0.0001" min="0" max="1" value="{float(rule.pix_discount_pct) if rule else 0.05}" required>
                    <small>Ex: 0.05 para 5%</small>
                </label>
                
                <label>
                    <strong>Margem Mínima (%):</strong>
                    <input type="number" name="margin_min_pct" step="0.0001" min="0" max="1" value="{float(rule.margin_min_pct) if rule else 0.10}" required>
                    <small>Ex: 0.10 para 10%</small>
                </label>
                
                <label>
                    <strong>Limite Total para Aprovação (R$, opcional):</strong>
                    <input type="number" name="approval_threshold_total" step="0.01" min="0" value="{float(rule.approval_threshold_total) if rule and rule.approval_threshold_total else ''}" placeholder="Deixe vazio se não aplicar">
                </label>
                
                <label>
                    <strong>Limite de Margem para Aprovação (%, opcional):</strong>
                    <input type="number" name="approval_threshold_margin" step="0.0001" min="0" max="1" value="{float(rule.approval_threshold_margin) if rule and rule.approval_threshold_margin else ''}" placeholder="Deixe vazio se não aplicar">
                    <small>Ex: 0.05 para 5%</small>
                </label>
                
                <button type="submit">Salvar Regras</button>
            </form>
            
            <p><a href="/">Voltar ao Dashboard</a></p>
        </body>
        </html>
        """
    )


@router.post("/rules/save", response_class=HTMLResponse)
async def rules_save(
    request: Request,
    pix_discount_pct: str = Form(...),
    margin_min_pct: str = Form(...),
    approval_threshold_total: str = Form(""),
    approval_threshold_margin: str = Form(""),
    _=Depends(require_tenant_host),
    db: Annotated[Session, Depends(get_db)] = None,
    __: None = Depends(require_csrf_token),
):
    """Save pricing rules."""
    tenant = request.state.tenant
    
    # Check authentication
    try:
        user = get_current_user(request, db)
    except HTTPException:
        slug = tenant.slug
        return RedirectResponse(
            url=f"https://orcazap.com/login?tenant={slug}&next=/rules",
            status_code=status.HTTP_302_FOUND,
        )

    try:
        pix_discount = Decimal(pix_discount_pct)
        margin_min = Decimal(margin_min_pct)
        approval_total = Decimal(approval_threshold_total) if approval_threshold_total.strip() else None
        approval_margin = Decimal(approval_threshold_margin) if approval_threshold_margin.strip() else None
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Valores inválidos")

    rule = db.query(PricingRule).filter_by(tenant_id=tenant.id).first()
    
    if rule:
        # Update existing
        rule.pix_discount_pct = pix_discount
        rule.margin_min_pct = margin_min
        rule.approval_threshold_total = approval_total
        rule.approval_threshold_margin = approval_margin
    else:
        # Create new
        rule = PricingRule(
            tenant_id=tenant.id,
            pix_discount_pct=pix_discount,
            margin_min_pct=margin_min,
            approval_threshold_total=approval_total,
            approval_threshold_margin=approval_margin,
        )
        db.add(rule)
    
    db.commit()
    
    return RedirectResponse(
        url="/rules",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/conversations", response_class=HTMLResponse)
async def conversations_list(
    request: Request,
    _=Depends(require_tenant_host),
    db: Annotated[Session, Depends(get_db)] = None,
):
    """List conversations."""
    tenant = request.state.tenant
    
    # Check authentication
    try:
        user = get_current_user(request, db)
    except HTTPException:
        slug = tenant.slug
        return RedirectResponse(
            url=f"https://orcazap.com/login?tenant={slug}&next=/conversations",
            status_code=status.HTTP_302_FOUND,
        )

    # Get filter
    state_filter = request.query_params.get("state", "")

    # Get conversations
    query = db.query(Conversation).filter_by(tenant_id=tenant.id)
    
    if state_filter:
        try:
            state_enum = ConversationState(state_filter)
            query = query.filter_by(state=state_enum)
        except ValueError:
            pass  # Invalid state, ignore filter
    
    conversations = query.order_by(desc(Conversation.last_message_at)).limit(50).all()

    # Get contacts for conversations
    conversations_data = []
    for conv in conversations:
        contact = db.query(Contact).filter_by(id=conv.contact_id).first()
        conversations_data.append({
            "conversation": conv,
            "contact": contact,
        })

    conversations_html = ""
    for data in conversations_data:
        conv = data["conversation"]
        contact = data["contact"]
        state_badge = {
            ConversationState.INBOUND: '<span style="background: #6c757d; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">Nova</span>',
            ConversationState.CAPTURE_MIN: '<span style="background: #17a2b8; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">Capturando</span>',
            ConversationState.QUOTE_READY: '<span style="background: #ffc107; color: black; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">Pronto</span>',
            ConversationState.QUOTE_SENT: '<span style="background: #28a745; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">Enviado</span>',
            ConversationState.WAITING_REPLY: '<span style="background: #17a2b8; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">Aguardando</span>',
            ConversationState.HUMAN_APPROVAL: '<span style="background: #dc3545; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">Aprovação</span>',
            ConversationState.WON: '<span style="background: #28a745; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">Ganho</span>',
            ConversationState.LOST: '<span style="background: #6c757d; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">Perdido</span>',
        }.get(conv.state, f'<span>{conv.state.value}</span>')
        
        conversations_html += f"""
        <tr>
            <td>{contact.phone if contact else 'N/A'}</td>
            <td>{contact.name if contact and contact.name else 'Sem nome'}</td>
            <td>{state_badge}</td>
            <td>{conv.last_message_at.strftime('%d/%m/%Y %H:%M') if conv.last_message_at else 'N/A'}</td>
            <td><a href="/conversations/{conv.id}">Ver</a></td>
        </tr>
        """

    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Conversas - {tenant.name}</title>
            <meta charset="utf-8">
            <script src="https://unpkg.com/htmx.org@1.9.10"></script>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }}
                th, td {{
                    padding: 10px;
                    text-align: left;
                    border: 1px solid #dee2e6;
                }}
                th {{
                    background: #f8f9fa;
                }}
                nav {{
                    margin: 20px 0;
                    padding: 10px 0;
                    border-bottom: 1px solid #dee2e6;
                }}
                nav a {{
                    margin-right: 20px;
                    color: #007bff;
                    text-decoration: none;
                }}
                select {{
                    padding: 8px;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                }}
            </style>
        </head>
        <body>
            <h1>Conversas</h1>
            <nav>
                <a href="/">Dashboard</a>
                <a href="/conversations">Conversas</a>
            </nav>
            
            <div style="margin: 20px 0;">
                <form method="GET" style="display: flex; gap: 10px; align-items: center;">
                    <label>
                        <strong>Filtrar por estado:</strong>
                        <select name="state" onchange="this.form.submit()">
                            <option value="">Todos</option>
                            <option value="INBOUND" {'selected' if state_filter == 'INBOUND' else ''}>Nova</option>
                            <option value="CAPTURE_MIN" {'selected' if state_filter == 'CAPTURE_MIN' else ''}>Capturando</option>
                            <option value="QUOTE_READY" {'selected' if state_filter == 'QUOTE_READY' else ''}>Pronto</option>
                            <option value="QUOTE_SENT" {'selected' if state_filter == 'QUOTE_SENT' else ''}>Enviado</option>
                            <option value="WAITING_REPLY" {'selected' if state_filter == 'WAITING_REPLY' else ''}>Aguardando</option>
                            <option value="HUMAN_APPROVAL" {'selected' if state_filter == 'HUMAN_APPROVAL' else ''}>Aprovação</option>
                            <option value="WON" {'selected' if state_filter == 'WON' else ''}>Ganho</option>
                            <option value="LOST" {'selected' if state_filter == 'LOST' else ''}>Perdido</option>
                        </select>
                    </label>
                </form>
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>Telefone</th>
                        <th>Nome</th>
                        <th>Estado</th>
                        <th>Última Mensagem</th>
                        <th>Ações</th>
                    </tr>
                </thead>
                <tbody>
                    {conversations_html if conversations_html else "<tr><td colspan='5'>Nenhuma conversa encontrada.</td></tr>"}
                </tbody>
            </table>
            
            <p><a href="/">Voltar ao Dashboard</a></p>
        </body>
        </html>
        """
    )


@router.get("/conversations/{conversation_id}", response_class=HTMLResponse)
async def conversation_detail(
    request: Request,
    conversation_id: UUID,
    _=Depends(require_tenant_host),
    db: Annotated[Session, Depends(get_db)] = None,
):
    """View conversation details."""
    tenant = request.state.tenant
    
    # Check authentication
    try:
        user = get_current_user(request, db)
    except HTTPException:
        slug = tenant.slug
        return RedirectResponse(
            url=f"https://orcazap.com/login?tenant={slug}&next=/conversations/{conversation_id}",
            status_code=status.HTTP_302_FOUND,
        )

    conversation = db.query(Conversation).filter_by(id=conversation_id, tenant_id=tenant.id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")

    contact = db.query(Contact).filter_by(id=conversation.contact_id).first()
    
    # Get messages
    messages = (
        db.query(Message)
        .filter_by(conversation_id=conversation_id)
        .order_by(Message.created_at)
        .all()
    )

    messages_html = ""
    for msg in messages:
        direction_class = "inbound" if msg.direction == MessageDirection.INBOUND else "outbound"
        direction_label = "Recebida" if msg.direction == MessageDirection.INBOUND else "Enviada"
        messages_html += f"""
        <div style="margin: 10px 0; padding: 10px; background: {'#e7f3ff' if direction_class == 'inbound' else '#f0f0f0'}; border-radius: 4px;">
            <strong>{direction_label}</strong> - {msg.created_at.strftime('%d/%m/%Y %H:%M')}<br>
            {msg.text_content or 'Mensagem sem texto'}
        </div>
        """

    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Conversa - {tenant.name}</title>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                nav a {{
                    margin-right: 20px;
                    color: #007bff;
                    text-decoration: none;
                }}
            </style>
        </head>
        <body>
            <h1>Conversa</h1>
            <nav>
                <a href="/conversations">← Voltar para Conversas</a>
            </nav>
            
            <div style="margin: 20px 0; padding: 15px; background: #f8f9fa; border-radius: 4px;">
                <strong>Contato:</strong> {contact.phone if contact else 'N/A'}<br>
                <strong>Nome:</strong> {contact.name if contact and contact.name else 'Sem nome'}<br>
                <strong>Estado:</strong> {conversation.state.value}<br>
                <strong>Última mensagem:</strong> {conversation.last_message_at.strftime('%d/%m/%Y %H:%M') if conversation.last_message_at else 'N/A'}
            </div>
            
            <h2>Mensagens</h2>
            {messages_html if messages_html else "<p>Nenhuma mensagem ainda.</p>"}
        </body>
        </html>
        """
    )


@router.get("/quotes", response_class=HTMLResponse)
async def quotes_list(
    request: Request,
    _=Depends(require_tenant_host),
    db: Annotated[Session, Depends(get_db)] = None,
):
    """List quotes."""
    tenant = request.state.tenant
    
    # Check authentication
    try:
        user = get_current_user(request, db)
    except HTTPException:
        slug = tenant.slug
        return RedirectResponse(
            url=f"https://orcazap.com/login?tenant={slug}&next=/quotes",
            status_code=status.HTTP_302_FOUND,
        )

    # Get filter
    status_filter = request.query_params.get("status", "")

    # Get quotes
    query = db.query(Quote).filter_by(tenant_id=tenant.id)
    
    if status_filter:
        try:
            status_enum = QuoteStatus(status_filter)
            query = query.filter_by(status=status_enum)
        except ValueError:
            pass  # Invalid status, ignore filter
    
    quotes = query.order_by(desc(Quote.created_at)).limit(50).all()

    # Get conversations and contacts for quotes
    quotes_data = []
    for quote in quotes:
        conversation = db.query(Conversation).filter_by(id=quote.conversation_id).first()
        contact = None
        if conversation:
            contact = db.query(Contact).filter_by(id=conversation.contact_id).first()
        quotes_data.append({
            "quote": quote,
            "conversation": conversation,
            "contact": contact,
        })

    quotes_html = ""
    for data in quotes_data:
        quote = data["quote"]
        contact = data["contact"]
        status_badge = {
            QuoteStatus.DRAFT: '<span style="background: #6c757d; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">Rascunho</span>',
            QuoteStatus.SENT: '<span style="background: #28a745; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">Enviado</span>',
            QuoteStatus.EXPIRED: '<span style="background: #ffc107; color: black; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">Expirado</span>',
            QuoteStatus.WON: '<span style="background: #28a745; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">Ganho</span>',
            QuoteStatus.LOST: '<span style="background: #dc3545; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">Perdido</span>',
        }.get(quote.status, f'<span>{quote.status.value}</span>')
        
        quotes_html += f"""
        <tr>
            <td>{contact.phone if contact else 'N/A'}</td>
            <td>R$ {float(quote.total):,.2f}</td>
            <td>{status_badge}</td>
            <td>{quote.created_at.strftime('%d/%m/%Y %H:%M') if quote.created_at else 'N/A'}</td>
            <td>{quote.valid_until.strftime('%d/%m/%Y %H:%M') if quote.valid_until else 'N/A'}</td>
            <td><a href="/quotes/{quote.id}">Ver</a></td>
        </tr>
        """

    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Orçamentos - {tenant.name}</title>
            <meta charset="utf-8">
            <script src="https://unpkg.com/htmx.org@1.9.10"></script>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }}
                th, td {{
                    padding: 10px;
                    text-align: left;
                    border: 1px solid #dee2e6;
                }}
                th {{
                    background: #f8f9fa;
                }}
                nav {{
                    margin: 20px 0;
                    padding: 10px 0;
                    border-bottom: 1px solid #dee2e6;
                }}
                nav a {{
                    margin-right: 20px;
                    color: #007bff;
                    text-decoration: none;
                }}
                select {{
                    padding: 8px;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                }}
            </style>
        </head>
        <body>
            <h1>Orçamentos</h1>
            <nav>
                <a href="/">Dashboard</a>
                <a href="/quotes">Orçamentos</a>
            </nav>
            
            <div style="margin: 20px 0;">
                <form method="GET" style="display: flex; gap: 10px; align-items: center;">
                    <label>
                        <strong>Filtrar por status:</strong>
                        <select name="status" onchange="this.form.submit()">
                            <option value="">Todos</option>
                            <option value="draft" {'selected' if status_filter == 'draft' else ''}>Rascunho</option>
                            <option value="sent" {'selected' if status_filter == 'sent' else ''}>Enviado</option>
                            <option value="expired" {'selected' if status_filter == 'expired' else ''}>Expirado</option>
                            <option value="won" {'selected' if status_filter == 'won' else ''}>Ganho</option>
                            <option value="lost" {'selected' if status_filter == 'lost' else ''}>Perdido</option>
                        </select>
                    </label>
                </form>
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>Contato</th>
                        <th>Total</th>
                        <th>Status</th>
                        <th>Criado em</th>
                        <th>Válido até</th>
                        <th>Ações</th>
                    </tr>
                </thead>
                <tbody>
                    {quotes_html if quotes_html else "<tr><td colspan='6'>Nenhum orçamento encontrado.</td></tr>"}
                </tbody>
            </table>
            
            <p><a href="/">Voltar ao Dashboard</a></p>
        </body>
        </html>
        """
    )


@router.get("/quotes/{quote_id}", response_class=HTMLResponse)
async def quote_detail(
    request: Request,
    quote_id: UUID,
    _=Depends(require_tenant_host),
    db: Annotated[Session, Depends(get_db)] = None,
):
    """View quote details."""
    tenant = request.state.tenant
    
    # Check authentication
    try:
        user = get_current_user(request, db)
    except HTTPException:
        slug = tenant.slug
        return RedirectResponse(
            url=f"https://orcazap.com/login?tenant={slug}&next=/quotes/{quote_id}",
            status_code=status.HTTP_302_FOUND,
        )

    quote = db.query(Quote).filter_by(id=quote_id, tenant_id=tenant.id).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")

    conversation = db.query(Conversation).filter_by(id=quote.conversation_id).first()
    contact = None
    if conversation:
        contact = db.query(Contact).filter_by(id=conversation.contact_id).first()

    items = quote.items_json if isinstance(quote.items_json, list) else []
    items_html = ""
    for item in items:
        items_html += f"""
        <tr>
            <td>{item.get('name', 'N/A')}</td>
            <td>{item.get('quantity', 0)} {item.get('unit', '')}</td>
            <td>R$ {float(item.get('unit_price', 0)):,.2f}</td>
            <td>R$ {float(item.get('total', 0)):,.2f}</td>
        </tr>
        """

    discount_amount = float(quote.subtotal) * float(quote.discount_pct)

    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Orçamento - {tenant.name}</title>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }}
                th, td {{
                    padding: 10px;
                    text-align: left;
                    border: 1px solid #dee2e6;
                }}
                th {{
                    background: #f8f9fa;
                }}
                nav a {{
                    margin-right: 20px;
                    color: #007bff;
                    text-decoration: none;
                }}
                .summary {{
                    margin: 20px 0;
                    padding: 15px;
                    background: #f8f9fa;
                    border-radius: 4px;
                }}
            </style>
        </head>
        <body>
            <h1>Orçamento</h1>
            <nav>
                <a href="/quotes">← Voltar para Orçamentos</a>
            </nav>
            
            <div class="summary">
                <strong>Contato:</strong> {contact.phone if contact else 'N/A'}<br>
                <strong>Status:</strong> {quote.status.value}<br>
                <strong>Criado em:</strong> {quote.created_at.strftime('%d/%m/%Y %H:%M') if quote.created_at else 'N/A'}<br>
                <strong>Válido até:</strong> {quote.valid_until.strftime('%d/%m/%Y %H:%M') if quote.valid_until else 'N/A'}
            </div>
            
            <h2>Itens</h2>
            <table>
                <thead>
                    <tr>
                        <th>Item</th>
                        <th>Quantidade</th>
                        <th>Preço Unit.</th>
                        <th>Total</th>
                    </tr>
                </thead>
                <tbody>
                    {items_html if items_html else "<tr><td colspan='4'>Nenhum item</td></tr>"}
                </tbody>
            </table>
            
            <div class="summary">
                <strong>Subtotal:</strong> R$ {float(quote.subtotal):,.2f}<br>
                <strong>Frete:</strong> R$ {float(quote.freight):,.2f}<br>
                {f'<strong>Desconto ({float(quote.discount_pct)*100:.0f}%):</strong> -R$ {discount_amount:,.2f}<br>' if float(quote.discount_pct) > 0 else ''}
                <strong>Total:</strong> R$ {float(quote.total):,.2f}<br>
                <strong>Margem:</strong> {float(quote.margin_pct)*100:.2f}%
            </div>
        </body>
        </html>
        """
    )

