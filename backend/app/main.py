import json, os, uuid, base64, hashlib, hmac, secrets, smtplib, ssl
from email.message import EmailMessage
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Generator, List
from fastapi import Depends, FastAPI, Header, HTTPException, Query, UploadFile, File, Request
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
load_dotenv()
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DATABASE_URL=os.getenv('DATABASE_URL','sqlite:///./veyra.db')
ADMIN_API_TOKEN=os.getenv('ADMIN_API_TOKEN','dev-only-change-me')
ORIGINS=[x.strip() for x in os.getenv('CORS_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(',') if x.strip()]
UPLOAD_DIR=os.path.abspath(os.getenv('UPLOAD_DIR', os.path.join(os.path.dirname(__file__), '..', 'uploads')))
os.makedirs(UPLOAD_DIR, exist_ok=True)
# Email notifications are optional in local development and fail safely if SMTP is unavailable.
EMAIL_NOTIFICATIONS_ENABLED=os.getenv('EMAIL_NOTIFICATIONS_ENABLED','false').strip().lower()=='true'
SMTP_HOST=os.getenv('SMTP_HOST','').strip()
SMTP_PORT=int(os.getenv('SMTP_PORT','587') or '587')
SMTP_USERNAME=os.getenv('SMTP_USERNAME','').strip()
SMTP_PASSWORD=os.getenv('SMTP_PASSWORD','')
SMTP_FROM_EMAIL=os.getenv('SMTP_FROM_EMAIL',SMTP_USERNAME).strip()
SMTP_FROM_NAME=os.getenv('SMTP_FROM_NAME','VEYRA').strip() or 'VEYRA'
SMTP_USE_TLS=os.getenv('SMTP_USE_TLS','true').strip().lower()=='true'

def email_notifications_ready()->bool:
 return bool(EMAIL_NOTIFICATIONS_ENABLED and SMTP_HOST and SMTP_FROM_EMAIL and SMTP_PORT>0)

def send_email_notification(to_email:str,subject:str,body:str)->bool:
 # Email failure must never roll back an order or fulfilment update. Never log SMTP credentials or message bodies.
 if not email_notifications_ready():
  print(f'[email] notifications disabled or SMTP incomplete; skipped: {subject}')
  return False
 try:
  msg=EmailMessage();msg['Subject']=f'{SMTP_FROM_NAME} | {subject}';msg['From']=f'{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>';msg['To']=to_email;msg.set_content(body)
  context=ssl.create_default_context()
  if SMTP_PORT==465:
   with smtplib.SMTP_SSL(SMTP_HOST,SMTP_PORT,timeout=8,context=context) as server:
    if SMTP_USERNAME: server.login(SMTP_USERNAME,SMTP_PASSWORD)
    server.send_message(msg)
  else:
   with smtplib.SMTP(SMTP_HOST,SMTP_PORT,timeout=8) as server:
    server.ehlo()
    if SMTP_USE_TLS: server.starttls(context=context);server.ehlo()
    if SMTP_USERNAME: server.login(SMTP_USERNAME,SMTP_PASSWORD)
    server.send_message(msg)
  print(f'[email] sent: {subject} to {to_email}')
  return True
 except Exception as exc:
  print(f'[email] delivery failed for {subject}: {type(exc).__name__}')
  return False

def notify_order(order: 'CustomerOrder',subject:str,intro:str,extra:str='')->bool:
 if not order or not order.customer_email: return False
 lines=[f'Hello {order.customer_name or "there"},','',intro,'',f'Order: {order.order_number}',f'Order status: {order.status.replace("_"," ").title()}',f'Payment status: {order.payment_status.replace("_"," ").title()}',f'Order total: INR {float(order.total):,.2f}']
 if extra: lines += ['',extra]
 lines += ['', 'This is an automated VEYRA development notification. If a payment or refund is mentioned as demo/manual, it does not mean money was moved automatically.', '']
 return send_email_notification(order.customer_email,subject,'\n'.join(lines))

MAX_IMAGE_BYTES=8 * 1024 * 1024
ALLOWED_IMAGE_TYPES={'image/jpeg':'.jpg','image/png':'.png'}
engine=create_engine(DATABASE_URL,connect_args={'check_same_thread':False} if DATABASE_URL.startswith('sqlite') else {},pool_pre_ping=True)
SessionLocal=sessionmaker(bind=engine,autoflush=False,expire_on_commit=False)
class Base(DeclarativeBase): pass
class Brand(Base):
 __tablename__='brands'
 id:Mapped[int]=mapped_column(Integer,primary_key=True)
 name:Mapped[str]=mapped_column(String(120),unique=True,index=True)
 slug:Mapped[str]=mapped_column(String(140),unique=True,index=True)
 description:Mapped[str]=mapped_column(Text,default='')
 logo_url:Mapped[str|None]=mapped_column(String(500),nullable=True)
 is_active:Mapped[bool]=mapped_column(Boolean,default=True)
 products:Mapped[list['Product']]=relationship(back_populates='brand')
class Product(Base):
 __tablename__='products'
 id:Mapped[int]=mapped_column(Integer,primary_key=True)
 brand_id:Mapped[int]=mapped_column(ForeignKey('brands.id'),index=True)
 name:Mapped[str]=mapped_column(String(180),index=True)
 category:Mapped[str]=mapped_column(String(80),index=True)
 price:Mapped[float]=mapped_column(Numeric(10,2))
 colour:Mapped[str]=mapped_column(String(80),default='—')
 image:Mapped[str]=mapped_column(String(1000),default='')
 description:Mapped[str]=mapped_column(Text,default='')
 sku:Mapped[str]=mapped_column(String(80),unique=True,index=True)
 stock:Mapped[int]=mapped_column(Integer,default=0)
 is_active:Mapped[bool]=mapped_column(Boolean,default=True)
 tag:Mapped[str|None]=mapped_column(String(50),nullable=True)
 brand:Mapped[Brand]=relationship(back_populates='products')
 gallery_images:Mapped[list['ProductImage']]=relationship(cascade='all, delete-orphan')
 variants:Mapped[list['ProductVariant']]=relationship(cascade='all, delete-orphan', order_by='ProductVariant.id')
class ProductImage(Base):
 __tablename__='product_images'
 id:Mapped[int]=mapped_column(Integer,primary_key=True)
 product_id:Mapped[int]=mapped_column(ForeignKey('products.id'),index=True)
 url:Mapped[str]=mapped_column(String(1000))
 sort_order:Mapped[int]=mapped_column(Integer,default=0)
class ProductVariant(Base):
 __tablename__='product_variants'
 id:Mapped[int]=mapped_column(Integer,primary_key=True)
 product_id:Mapped[int]=mapped_column(ForeignKey('products.id'),index=True)
 colour:Mapped[str]=mapped_column(String(80),index=True)
 size:Mapped[str]=mapped_column(String(20),index=True)
 sku:Mapped[str]=mapped_column(String(100),unique=True,index=True)
 stock:Mapped[int]=mapped_column(Integer,default=0)
 images_json:Mapped[str]=mapped_column(Text,default='[]')

class Customer(Base):
 __tablename__='customers'
 id:Mapped[int]=mapped_column(Integer,primary_key=True)
 email:Mapped[str]=mapped_column(String(255),unique=True,index=True)
 password_hash:Mapped[str]=mapped_column(String(300))
 name:Mapped[str]=mapped_column(String(180),default='')
 phone:Mapped[str|None]=mapped_column(String(30),nullable=True)
 addresses_json:Mapped[str]=mapped_column(Text,default='[]')
 favourites_json:Mapped[str]=mapped_column(Text,default='[]')
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class AdminStaff(Base):
 __tablename__='admin_staff'
 id:Mapped[int]=mapped_column(Integer,primary_key=True)
 name:Mapped[str]=mapped_column(String(180))
 email:Mapped[str]=mapped_column(String(255),unique=True,index=True)
 password_hash:Mapped[str]=mapped_column(String(300))
 role:Mapped[str]=mapped_column(String(20),default='worker')
 is_active:Mapped[bool]=mapped_column(Boolean,default=True)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class AdminSession(Base):
 __tablename__='admin_sessions'
 id:Mapped[int]=mapped_column(Integer,primary_key=True)
 token_hash:Mapped[str]=mapped_column(String(64),unique=True,index=True)
 staff_id:Mapped[int]=mapped_column(ForeignKey('admin_staff.id'),index=True)
 expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
 staff:Mapped[AdminStaff]=relationship()
class AppSetting(Base):
 __tablename__='app_settings'
 key:Mapped[str]=mapped_column(String(100),primary_key=True)
 value:Mapped[str]=mapped_column(String(500),default='')
 updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),onupdate=lambda:datetime.now(timezone.utc))

class CustomerOrder(Base):
 __tablename__='orders'
 id:Mapped[int]=mapped_column(Integer,primary_key=True)
 order_number:Mapped[str]=mapped_column(String(40),unique=True,index=True)
 customer_email:Mapped[str]=mapped_column(String(255),index=True)
 customer_id:Mapped[int|None]=mapped_column(ForeignKey('customers.id'),nullable=True,index=True)
 status:Mapped[str]=mapped_column(String(40),default='pending_payment')
 payment_method:Mapped[str]=mapped_column(String(30),default='mock_online')
 payment_status:Mapped[str]=mapped_column(String(30),default='unpaid_demo')
 total:Mapped[float]=mapped_column(Numeric(12,2),default=0)
 customer_name:Mapped[str|None]=mapped_column(String(180),nullable=True)
 phone:Mapped[str|None]=mapped_column(String(30),nullable=True)
 shipping_json:Mapped[str]=mapped_column(Text,default='{}')
 delivery_method:Mapped[str]=mapped_column(String(30),default='standard')
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
 suborders:Mapped[list['BrandSuborder']]=relationship(back_populates='order',cascade='all, delete-orphan')
class BrandSuborder(Base):
 __tablename__='brand_suborders'
 id:Mapped[int]=mapped_column(Integer,primary_key=True)
 order_id:Mapped[int]=mapped_column(ForeignKey('orders.id'),index=True)
 brand_id:Mapped[int]=mapped_column(ForeignKey('brands.id'),index=True)
 status:Mapped[str]=mapped_column(String(40),default='awaiting_payment')
 subtotal:Mapped[float]=mapped_column(Numeric(12,2),default=0)
 shipment_tracking_number:Mapped[str|None]=mapped_column(String(120),nullable=True)
 items_json:Mapped[str]=mapped_column(Text,default='[]')
 order:Mapped[CustomerOrder]=relationship(back_populates='suborders')
 brand:Mapped[Brand]=relationship()
class OrderServiceRequest(Base):
 __tablename__='order_service_requests'
 id:Mapped[int]=mapped_column(Integer,primary_key=True)
 order_id:Mapped[int]=mapped_column(ForeignKey('orders.id'),index=True)
 customer_id:Mapped[int|None]=mapped_column(ForeignKey('customers.id'),nullable=True,index=True)
 request_type:Mapped[str]=mapped_column(String(20),index=True)  # cancellation or return
 reason:Mapped[str]=mapped_column(Text)
 status:Mapped[str]=mapped_column(String(30),default='requested',index=True)
 refund_status:Mapped[str]=mapped_column(String(30),default='not_applicable')
 admin_note:Mapped[str]=mapped_column(Text,default='')
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
 updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),onupdate=lambda:datetime.now(timezone.utc))
 order:Mapped['CustomerOrder']=relationship()
 customer:Mapped['Customer|None']=relationship()

class OrderServiceRequestInput(BaseModel):
 request_type:str=Field(pattern=r'^(cancellation|return)$')
 reason:str=Field(min_length=5,max_length=1000)

class BrandInput(BaseModel):
 name:str=Field(min_length=2,max_length=120)
 slug:str=Field(min_length=2,max_length=140,pattern=r'^[a-z0-9-]+$')
 description:str=''
 logo_url:str|None=None
 is_active:bool=True
class ProductInput(BaseModel):
 brand_id:int
 name:str=Field(min_length=2,max_length=180)
 category:str
 price:float=Field(gt=0)
 colour:str='—'
 image:str=''
 images:list[str]=Field(default_factory=list,max_length=12)
 description:str=''
 sku:str=Field(min_length=2,max_length=80)
 stock:int=Field(ge=0)
 variants:list[dict]=Field(default_factory=list,max_length=120)
 is_active:bool=True
 tag:str|None=None
class OrderLine(BaseModel):
 product_id:int
 variant_id:int|None=None
 colour:str|None=None
 size:str|None=None
 quantity:int=Field(ge=1,le=20)
class OrderInput(BaseModel):
 customer_email:str=Field(min_length=5,max_length=255)
 customer_name:str|None=None
 phone:str|None=None
 shipping_address:str|None=None
 city:str|None=None
 state:str|None=None
 pincode:str|None=None
 delivery_method:str='standard'
 payment_method:str='mock_online'
 items:list[OrderLine]=Field(min_length=1)

class CustomerRegister(BaseModel):
 email:str=Field(min_length=5,max_length=255)
 password:str=Field(min_length=10,max_length=128)
 name:str=Field(min_length=2,max_length=180)
 phone:str|None=None
class CustomerLogin(BaseModel):
 email:str=Field(min_length=5,max_length=255)
 password:str=Field(min_length=1,max_length=128)
class AdminLoginInput(BaseModel):
 email:str=Field(min_length=5,max_length=255)
 password:str=Field(min_length=1,max_length=128)
class AdminBootstrapInput(BaseModel):
 name:str=Field(min_length=2,max_length=180)
 email:str=Field(min_length=5,max_length=255)
 password:str=Field(min_length=12,max_length=128)
class AdminStaffCreateInput(BaseModel):
 name:str=Field(min_length=2,max_length=180)
 email:str=Field(min_length=5,max_length=255)
 password:str=Field(min_length=12,max_length=128)
 role:str=Field(pattern=r'^(founder|manager|worker)$')
class CustomerUpdate(BaseModel):
 name:str|None=Field(default=None,min_length=2,max_length=180)
 phone:str|None=Field(default=None,max_length=30)
 addresses:list[dict]|None=Field(default=None,max_length=20)
 favourites:list[int]|None=Field(default=None,max_length=500)

def password_hash(password:str,salt:bytes|None=None)->str:
 salt=salt or secrets.token_bytes(16)
 digest=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),salt,310000)
 return 'pbkdf2_sha256$310000$'+base64.urlsafe_b64encode(salt).decode().rstrip('=')+'$'+base64.urlsafe_b64encode(digest).decode().rstrip('=')
def password_verify(password:str,encoded:str)->bool:
 try:
  algorithm,rounds,salt,digest=encoded.split('$')
  if algorithm!='pbkdf2_sha256':return False
  raw_salt=base64.urlsafe_b64decode(salt+'='*((4-len(salt)%4)%4))
  expected=base64.urlsafe_b64decode(digest+'='*((4-len(digest)%4)%4))
  actual=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),raw_salt,int(rounds))
  return hmac.compare_digest(actual,expected)
 except Exception:return False
def token_secret()->bytes:
 secret=os.getenv('CUSTOMER_TOKEN_SECRET','')
 if len(secret)<32: raise HTTPException(503,'Set CUSTOMER_TOKEN_SECRET to a random value of at least 32 characters in backend/.env.')
 return secret.encode()
def issue_token(customer:Customer)->str:
 payload={'sub':customer.id,'exp':int((datetime.now(timezone.utc)+timedelta(days=7)).timestamp()),'nonce':secrets.token_hex(8)}
 body=base64.urlsafe_b64encode(json.dumps(payload,separators=(',',':')).encode()).decode().rstrip('=')
 sig=base64.urlsafe_b64encode(hmac.new(token_secret(),body.encode(),hashlib.sha256).digest()).decode().rstrip('=')
 return body+'.'+sig

def db_session()->Generator[Session,None,None]:
 db=SessionLocal()
 try: yield db
 finally: db.close()
def current_customer(authorization:str|None=Header(default=None),db:Session=Depends(db_session)):
 # This dependency is replaced below with a request-scoped DB dependency to ensure sessions close.
 if not authorization or not authorization.startswith('Bearer '):raise HTTPException(401,'Sign in to access your account.')
 token=authorization[7:].strip()
 try:
  body,sig=token.split('.',1)
  expected=base64.urlsafe_b64encode(hmac.new(token_secret(),body.encode(),hashlib.sha256).digest()).decode().rstrip('=')
  if not hmac.compare_digest(sig,expected):raise ValueError()
  payload=json.loads(base64.urlsafe_b64decode(body+'='*((4-len(body)%4)%4)))
  if int(payload['exp'])<int(datetime.now(timezone.utc).timestamp()):raise HTTPException(401,'Your session has expired. Please sign in again.')
  customer=db.get(Customer,int(payload['sub']))
  if not customer:raise ValueError()
  return customer
 except HTTPException:raise
 except Exception:raise HTTPException(401,'Invalid customer session. Please sign in again.')


def admin_guard(request:Request,x_admin_token:str|None=Header(default=None),db:Session=Depends(db_session))->AdminStaff:
 if not x_admin_token: raise HTTPException(401,'Your admin session has ended. Please sign in again.')
 digest=hashlib.sha256(x_admin_token.encode()).hexdigest()
 session=db.scalar(select(AdminSession).where(AdminSession.token_hash==digest))
 if not session: raise HTTPException(401,'Invalid admin session. Please sign in again.')
 expires=session.expires_at
 if expires.tzinfo is None: expires=expires.replace(tzinfo=timezone.utc)
 if expires < datetime.now(timezone.utc):
  db.delete(session);db.commit();raise HTTPException(401,'Your admin session has expired. Please sign in again.')
 staff=db.get(AdminStaff,session.staff_id)
 if not staff or not staff.is_active: raise HTTPException(401,'This staff account is inactive. Contact an administrator.')
 path=request.url.path;method=request.method.upper()
 if staff.role=='worker':
  allowed=(path=='/api/v1/admin/auth/me' and method=='GET') or (path=='/api/v1/admin/orders' and method=='GET') or (path.startswith('/api/v1/admin/suborders/') and method=='PATCH')
  if not allowed: raise HTTPException(403,'Worker accounts can only view orders and update assigned parcel details.')
 elif staff.role=='manager' and path.startswith('/api/v1/admin/settings'):
  raise HTTPException(403,'Only a Founder can change marketplace settings.')
 return staff

def issue_admin_session(db:Session,staff:AdminStaff)->str:
 # The raw token is only returned once. The browser keeps it in sessionStorage,
 # which is cleared when that browser tab/session closes; the server stores only its hash.
 raw=secrets.token_urlsafe(40)
 db.add(AdminSession(token_hash=hashlib.sha256(raw.encode()).hexdigest(),staff_id=staff.id,expires_at=datetime.now(timezone.utc)+timedelta(hours=12)))
 db.commit()
 return raw

def staff_json(staff:AdminStaff):
 return {'id':staff.id,'name':staff.name,'email':staff.email,'role':staff.role,'is_active':staff.is_active,'created_at':staff.created_at.isoformat() if staff.created_at else None}
def product_json(p:Product):
 gallery=[row.url for row in sorted(p.gallery_images,key=lambda item:item.sort_order)]
 variants=[{'id':v.id,'colour':v.colour,'size':v.size,'sku':v.sku,'stock':v.stock,'images':json.loads(v.images_json or '[]')} for v in p.variants]
 return {'id':p.id,'brand_id':p.brand_id,'brand':p.brand.name,'brand_name':p.brand.name,'name':p.name,'category':p.category,'price':float(p.price),'colour':p.colour,'image':p.image,'images':gallery or ([p.image] if p.image else []),'description':p.description,'sku':p.sku,'stock':sum(v['stock'] for v in variants) if variants else p.stock,'variants':variants,'is_active':p.is_active,'tag':p.tag}
def seed(db:Session):
 if db.scalar(select(Brand.id).limit(1)) is not None:return
 brands=[Brand(name='NORTH OBJECTS',slug='north-objects',description='Everyday essentials.'),Brand(name='COMMON FORM',slug='common-form',description='Modern classics.'),Brand(name='STUDIO 04',slug='studio-04',description='Utility, refined.'),Brand(name='FORM & FIELD',slug='form-field',description='Texture and form.')]
 db.add_all(brands);db.flush()
 rows=[('Heavyweight Boxy Tee','T-shirts',899,'Stone','https://images.unsplash.com/photo-1618354691373-d851c5c3a990?auto=format&fit=crop&w=900&q=85','NO-TEE-001',24,'BESTSELLER',0),('Relaxed Oxford Shirt','Shirts',1699,'Blue stripe','https://images.unsplash.com/photo-1603252109303-2751441dd157?auto=format&fit=crop&w=900&q=85','CF-SHR-001',15,'NEW IN',1),('Everyday Pleated Trouser','Trousers',2199,'Charcoal','https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=900&q=85','S04-TR-001',12,None,2),('Structured Overshirt','Outerwear',2499,'Olive','https://images.unsplash.com/photo-1591047139829-d91aecb6caea?auto=format&fit=crop&w=900&q=85','NO-OUT-001',8,'EDITOR’S PICK',0),('Essential Cotton Tee','T-shirts',799,'Off-white','https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=900&q=85','CF-TEE-001',30,None,1),('Weekend Knit Polo','Knitwear',1899,'Sand','https://images.unsplash.com/photo-1627225924765-552d49cf47ad?auto=format&fit=crop&w=900&q=85','FF-KN-001',9,'LIMITED RUN',3),('Utility Straight Fit','Trousers',1999,'Moss','https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=900&q=85','S04-TR-002',14,None,2),('Soft Structure Shirt','Shirts',1799,'Ecru','https://images.unsplash.com/photo-1603252109303-2751441dd157?auto=format&fit=crop&w=900&q=85','FF-SHR-001',11,None,3)]
 for n,c,price,col,img,sku,stock,tag,bi in rows:db.add(Product(brand_id=brands[bi].id,name=n,category=c,price=price,colour=col,image=img,sku=sku,stock=stock,tag=tag,description=f'{n}, selected for the VEYRA concept catalogue.'))
 db.commit()
@asynccontextmanager
async def lifespan(app:FastAPI):
 Base.metadata.create_all(bind=engine)
 # Lightweight additive migration for existing local SQLite databases.
 if DATABASE_URL.startswith('sqlite'):
  from sqlalchemy import inspect, text
  with engine.begin() as conn:
   columns={col['name'] for col in inspect(engine).get_columns('orders')}
   for name,definition in [('customer_id','INTEGER'),('customer_name','VARCHAR(180)'),('phone','VARCHAR(30)'),('shipping_json',"TEXT NOT NULL DEFAULT '{}'"),('delivery_method',"VARCHAR(30) NOT NULL DEFAULT 'standard'"),('payment_method',"VARCHAR(30) NOT NULL DEFAULT 'mock_online'"),('payment_status',"VARCHAR(30) NOT NULL DEFAULT 'unpaid_demo'")]:
    if name not in columns: conn.execute(text(f'ALTER TABLE orders ADD COLUMN {name} {definition}'))
 with SessionLocal() as db:
  seed(db)
  # Backfill legacy products without inventing historical size counts: preserve their old total at size M.
  for product in db.scalars(select(Product)).all():
   if not product.variants:
    for size in ['XS','S','M','L','XL','XXL']:
     db.add(ProductVariant(product_id=product.id,colour=product.colour or 'Default',size=size,sku=f'{product.sku}-{size}',stock=product.stock if size=='M' else 0,images_json=json.dumps([x.url for x in sorted(product.gallery_images,key=lambda x:x.sort_order)] or ([product.image] if product.image else []))))
  db.commit()
 yield
app=FastAPI(title='VEYRA Marketplace API',version='0.1.0',lifespan=lifespan,description='Development API for a curated multi-brand fashion marketplace.')
app.mount('/uploads', StaticFiles(directory=UPLOAD_DIR), name='uploads')
app.add_middleware(CORSMiddleware,allow_origins=ORIGINS,allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
class NotificationTestInput(BaseModel):
 email:str=Field(min_length=5,max_length=255)

@app.get('/health')
def health():return {'status':'ok','service':'veyra-api'}

@app.get('/api/v1/admin/notifications/status',dependencies=[Depends(admin_guard)])
def notification_status():
 return {'enabled':EMAIL_NOTIFICATIONS_ENABLED,'configured':email_notifications_ready(),'smtp_host_set':bool(SMTP_HOST),'from_email_set':bool(SMTP_FROM_EMAIL),'note':'Email notifications are sent only when EMAIL_NOTIFICATIONS_ENABLED=true and SMTP settings are complete.'}

@app.post('/api/v1/admin/notifications/test',dependencies=[Depends(admin_guard)])
def test_notification(payload:NotificationTestInput):
 if not email_notifications_ready(): raise HTTPException(503,'Email is not configured. Set EMAIL_NOTIFICATIONS_ENABLED and SMTP settings in backend/.env, then restart the backend.')
 ok=send_email_notification(payload.email.strip(),'Test notification','Your VEYRA email notification settings are working. This is a test message; no order or payment action was performed.')
 if not ok: raise HTTPException(502,'SMTP test delivery failed. Check the SMTP host, port, TLS, sender and credentials in backend/.env.')
 return {'sent':True,'to':payload.email.strip(),'message':'Test email sent.'}

@app.post('/api/v1/admin/auth/bootstrap',status_code=201)
def bootstrap_founder(payload:AdminBootstrapInput,x_admin_token:str|None=Header(default=None),db:Session=Depends(db_session)):
 # One-time setup: the existing backend admin token may create the first Founder only.
 if not ADMIN_API_TOKEN or ADMIN_API_TOKEN=='dev-only-change-me': raise HTTPException(503,'Set a strong ADMIN_API_TOKEN in backend/.env before first-time Founder setup.')
 if not hmac.compare_digest(x_admin_token or '',ADMIN_API_TOKEN): raise HTTPException(401,'Invalid setup token.')
 if db.scalar(select(AdminStaff.id).limit(1)) is not None: raise HTTPException(409,'Founder setup is already complete. Sign in with your staff account.')
 staff=AdminStaff(name=payload.name.strip(),email=payload.email.strip().lower(),password_hash=password_hash(payload.password),role='founder',is_active=True)
 db.add(staff)
 try: db.commit();db.refresh(staff)
 except Exception: db.rollback();raise HTTPException(409,'Could not create Founder account. Check that the email is unique.')
 token=issue_admin_session(db,staff)
 return {'access_token':token,'token_type':'session','staff':staff_json(staff)}

@app.post('/api/v1/admin/auth/login')
def admin_login(payload:AdminLoginInput,db:Session=Depends(db_session)):
 staff=db.scalar(select(AdminStaff).where(AdminStaff.email==payload.email.strip().lower()))
 if not staff or not staff.is_active or not password_verify(payload.password,staff.password_hash): raise HTTPException(401,'Email or password is incorrect.')
 token=issue_admin_session(db,staff)
 return {'access_token':token,'token_type':'session','staff':staff_json(staff)}

@app.get('/api/v1/admin/auth/me')
def admin_me(staff:AdminStaff=Depends(admin_guard)):
 return staff_json(staff)

@app.post('/api/v1/admin/auth/logout')
def admin_logout(x_admin_token:str|None=Header(default=None),staff:AdminStaff=Depends(admin_guard),db:Session=Depends(db_session)):
 digest=hashlib.sha256((x_admin_token or '').encode()).hexdigest()
 session=db.scalar(select(AdminSession).where(AdminSession.token_hash==digest))
 if session: db.delete(session);db.commit()
 return {'ok':True}

@app.post('/api/v1/admin/staff',status_code=201)
def create_admin_staff(payload:AdminStaffCreateInput,staff:AdminStaff=Depends(admin_guard),db:Session=Depends(db_session)):
 if staff.role not in ('founder','manager'): raise HTTPException(403,'Only Founders and Managers can create staff accounts.')
 if staff.role=='manager' and payload.role!='worker': raise HTTPException(403,'Managers may create Worker accounts only. A Founder must create Manager or Founder accounts.')
 email=payload.email.strip().lower()
 if db.scalar(select(AdminStaff.id).where(AdminStaff.email==email)) is not None: raise HTTPException(409,'An account with this email already exists.')
 created=AdminStaff(name=payload.name.strip(),email=email,password_hash=password_hash(payload.password),role=payload.role,is_active=True)
 db.add(created)
 try: db.commit();db.refresh(created)
 except Exception: db.rollback();raise HTTPException(409,'Could not create staff account.')
 return staff_json(created)

@app.get('/api/v1/admin/staff')
def list_admin_staff(staff:AdminStaff=Depends(admin_guard),db:Session=Depends(db_session)):
 if staff.role not in ('founder','manager'): raise HTTPException(403,'Only Founders and Managers can view staff accounts.')
 rows=list(db.scalars(select(AdminStaff).order_by(AdminStaff.id)).all())
 return [staff_json(row) for row in rows]

@app.patch('/api/v1/admin/staff/{staff_id}')
def update_admin_staff(staff_id:int,payload:dict,staff:AdminStaff=Depends(admin_guard),db:Session=Depends(db_session)):
 if staff.role!='founder': raise HTTPException(403,'Only a Founder can change staff roles or deactivate accounts.')
 target=db.get(AdminStaff,staff_id)
 if not target: raise HTTPException(404,'Staff account not found.')
 if target.id==staff.id and payload.get('is_active') is False: raise HTTPException(400,'You cannot deactivate your own account.')
 if 'is_active' in payload: target.is_active=bool(payload['is_active'])
 if 'role' in payload:
  if payload['role'] not in ('founder','manager','worker'): raise HTTPException(422,'Invalid role.')
  target.role=payload['role']
 db.commit();db.refresh(target)
 return staff_json(target)
@app.post('/api/v1/auth/register',status_code=201)
def register_customer(payload:CustomerRegister,db:Session=Depends(db_session)):
 token_secret()  # Fail before writing a customer if session signing is not configured.
 email=payload.email.strip().lower()
 if '@' not in email or '.' not in email.rsplit('@',1)[-1]:raise HTTPException(422,'Enter a valid email address.')
 if db.scalar(select(Customer.id).where(Customer.email==email)):raise HTTPException(409,'An account with this email already exists. Sign in instead.')
 customer=Customer(email=email,password_hash=password_hash(payload.password),name=payload.name.strip(),phone=(payload.phone or '').strip() or None)
 db.add(customer);db.commit();db.refresh(customer)
 return {'access_token':issue_token(customer),'token_type':'bearer','expires_in':604800,'customer':customer_json(customer)}
@app.post('/api/v1/auth/login')
def login_customer(payload:CustomerLogin,db:Session=Depends(db_session)):
 token_secret()  # Fail clearly if customer sessions are not configured.
 customer=db.scalar(select(Customer).where(Customer.email==payload.email.strip().lower()))
 if not customer or not password_verify(payload.password,customer.password_hash):raise HTTPException(401,'Email or password is incorrect.')
 return {'access_token':issue_token(customer),'token_type':'bearer','expires_in':604800,'customer':customer_json(customer)}
def customer_json(customer:Customer):
 return {'id':customer.id,'email':customer.email,'name':customer.name,'phone':customer.phone,'addresses':json.loads(customer.addresses_json or '[]'),'favourites':json.loads(customer.favourites_json or '[]'),'created_at':customer.created_at.isoformat() if customer.created_at else None}
@app.get('/api/v1/auth/me')
def get_customer_profile(customer:Customer=Depends(current_customer)):
 return customer_json(customer)
@app.patch('/api/v1/auth/me')
def update_customer_profile(payload:CustomerUpdate,customer:Customer=Depends(current_customer),db:Session=Depends(db_session)):
 # Resolve the authenticated customer again in the request's DB session before writing.
 target=db.get(Customer,customer.id)
 if not target:raise HTTPException(401,'Customer account not found.')
 data=payload.model_dump(exclude_unset=True)
 if 'name' in data and data['name'] is not None:target.name=data['name'].strip()
 if 'phone' in data:target.phone=(data['phone'] or '').strip() or None
 if 'addresses' in data and data['addresses'] is not None:
  if any(not isinstance(a,dict) or not all(k in a for k in ('label','address','city','state','pincode')) for a in data['addresses']):raise HTTPException(422,'Each address needs label, address, city, state and pincode.')
  target.addresses_json=json.dumps(data['addresses'])
 if 'favourites' in data and data['favourites'] is not None:target.favourites_json=json.dumps(sorted(set(int(x) for x in data['favourites'] if int(x)>0)))
 db.commit();db.refresh(target);return customer_json(target)
@app.get('/api/v1/account/orders')
def customer_order_history(customer:Customer=Depends(current_customer),db:Session=Depends(db_session)):
 orders=list(db.scalars(select(CustomerOrder).where(CustomerOrder.customer_id==customer.id).order_by(CustomerOrder.id.desc()).limit(100)).all())
 return [{'id':o.id,'order_number':o.order_number,'status':o.status,'total':float(o.total),'created_at':o.created_at.isoformat() if o.created_at else None,'shipping':json.loads(o.shipping_json or '{}'),'delivery_method':o.delivery_method,'suborders':[{'brand':so.brand.name,'status':so.status,'tracking':so.shipment_tracking_number,'items':json.loads(so.items_json or '[]')} for so in o.suborders]} for o in orders]

@app.get('/api/v1/brands')
def list_brands(active_only:bool=True,db:Session=Depends(db_session)):
 stmt=select(Brand).order_by(Brand.name)
 if active_only:stmt=stmt.where(Brand.is_active.is_(True))
 return [{'id':b.id,'name':b.name,'slug':b.slug,'description':b.description,'logo_url':b.logo_url,'is_active':b.is_active} for b in db.scalars(stmt).all()]
@app.get('/api/v1/products')
def list_products(q:str|None=None,category:str|None=None,brand_id:int|None=None,min_price:float|None=Query(default=None,ge=0),max_price:float|None=Query(default=None,ge=0),sort:str='featured',db:Session=Depends(db_session)):
 stmt=select(Product).join(Brand).where(Product.is_active.is_(True),Brand.is_active.is_(True))
 if q:
  term=f'%{q.strip()}%';stmt=stmt.where((Product.name.ilike(term))|(Product.category.ilike(term))|(Brand.name.ilike(term)))
 if category:stmt=stmt.where(Product.category==category)
 if brand_id:stmt=stmt.where(Product.brand_id==brand_id)
 if min_price is not None:stmt=stmt.where(Product.price>=min_price)
 if max_price is not None:stmt=stmt.where(Product.price<=max_price)
 products=list(db.scalars(stmt).all())
 if sort=='low':products.sort(key=lambda p:float(p.price))
 elif sort=='high':products.sort(key=lambda p:float(p.price),reverse=True)
 elif sort=='new':products.sort(key=lambda p:p.id,reverse=True)
 return [product_json(p) for p in products]
@app.get('/api/v1/products/{product_id}')
def get_product(product_id:int,db:Session=Depends(db_session)):
 p=db.scalar(select(Product).where(Product.id==product_id,Product.is_active.is_(True)))
 if not p:raise HTTPException(404,'Product not found.')
 return product_json(p)
@app.get('/api/v1/admin/brands',dependencies=[Depends(admin_guard)])
def admin_list_brands(active_only:bool=False,db:Session=Depends(db_session)):
 stmt=select(Brand).order_by(Brand.name)
 if active_only:stmt=stmt.where(Brand.is_active.is_(True))
 return [{'id':b.id,'name':b.name,'slug':b.slug,'description':b.description,'logo_url':b.logo_url,'is_active':b.is_active} for b in db.scalars(stmt).all()]
@app.get('/api/v1/admin/products',dependencies=[Depends(admin_guard)])
def admin_list_products(db:Session=Depends(db_session)):
 return [product_json(p) for p in db.scalars(select(Product).order_by(Product.id.desc())).all()]
@app.post('/api/v1/admin/uploads/images',dependencies=[Depends(admin_guard)])
async def upload_product_images(files: List[UploadFile] = File(...)):
 if not files: raise HTTPException(422, 'Choose at least one JPG or PNG image.')
 if len(files)>12: raise HTTPException(422, 'Upload at most 12 images at a time.')
 saved=[]
 try:
  for file in files:
   content_type=(file.content_type or '').lower()
   if content_type not in ALLOWED_IMAGE_TYPES:
    raise HTTPException(415, f'{file.filename or "File"}: only JPG/JPEG and PNG images are supported.')
   data=await file.read(MAX_IMAGE_BYTES+1)
   if not data: raise HTTPException(422, f'{file.filename or "File"} is empty.')
   if len(data)>MAX_IMAGE_BYTES: raise HTTPException(413, f'{file.filename or "File"} exceeds the 8 MB limit.')
   valid_jpeg=data.startswith(bytes.fromhex('ffd8ff'))
   valid_png=data.startswith(bytes.fromhex('89504e470d0a1a0a'))
   if not ((content_type=='image/jpeg' and valid_jpeg) or (content_type=='image/png' and valid_png)):
    raise HTTPException(415, f'{file.filename or "File"} does not match its declared image type.')
   ext=ALLOWED_IMAGE_TYPES[content_type]
   filename=f'{uuid.uuid4().hex}{ext}'
   with open(os.path.join(UPLOAD_DIR,filename),'wb') as out: out.write(data)
   saved.append({'url':f'/uploads/{filename}','filename':filename,'content_type':content_type,'size':len(data)})
  return {'images':saved}
 except Exception:
  for item in saved:
   try: os.remove(os.path.join(UPLOAD_DIR,item['filename']))
   except OSError: pass
  raise
@app.patch('/api/v1/admin/brands/{brand_id}',dependencies=[Depends(admin_guard)])
def admin_update_brand(brand_id:int,payload:dict,db:Session=Depends(db_session)):
 b=db.get(Brand,brand_id)
 if not b:raise HTTPException(404,'Brand not found.')
 allowed={'name','slug','description','logo_url','is_active'}
 if set(payload)-allowed:raise HTTPException(422,'Unsupported brand fields.')
 for key,value in payload.items():setattr(b,key,value)
 db.commit();db.refresh(b)
 return {'id':b.id,'name':b.name,'slug':b.slug,'description':b.description,'logo_url':b.logo_url,'is_active':b.is_active}
@app.post('/api/v1/admin/brands',dependencies=[Depends(admin_guard)],status_code=201)
def create_brand(payload:BrandInput,db:Session=Depends(db_session)):
 if db.scalar(select(Brand).where((Brand.slug==payload.slug)|(Brand.name==payload.name))):raise HTTPException(409,'Brand name or slug already exists.')
 b=Brand(**payload.model_dump());db.add(b);db.commit();db.refresh(b)
 return {'id':b.id,'name':b.name,'slug':b.slug,'description':b.description,'is_active':b.is_active}
def save_variants(db:Session,p:Product,rows:list[dict],default_images:list[str]):
 cleaned=[]; seen=set(); skus=set()
 for row in rows:
  colour=str(row.get('colour',p.colour)).strip()[:80]; size=str(row.get('size','')).strip().upper()[:20]; sku=str(row.get('sku') or f'{p.sku}-{colour}-{size}').strip()[:100]
  try: stock=int(row.get('stock',0))
  except (TypeError,ValueError): raise HTTPException(422,'Variant stock must be a whole number.')
  if not colour or not size or stock<0: raise HTTPException(422,'Every variant needs a colour, size, and non-negative stock.')
  key=(colour.casefold(),size)
  if key in seen: raise HTTPException(422,f'Duplicate variant: {colour} / {size}.')
  if sku in skus: raise HTTPException(422,f'Duplicate variant SKU: {sku}.')
  existing=db.scalar(select(ProductVariant).where(ProductVariant.sku==sku,ProductVariant.product_id!=p.id))
  if existing: raise HTTPException(409,f'Variant SKU already exists: {sku}.')
  seen.add(key);skus.add(sku);imgs=row.get('images',default_images)
  if not isinstance(imgs,list) or len(imgs)>12 or any(not isinstance(x,str) or len(x)>1000 for x in imgs): raise HTTPException(422,'Variant images must be a list of up to 12 URLs.')
  cleaned.append({'colour':colour,'size':size,'sku':sku,'stock':stock,'images_json':json.dumps(list(dict.fromkeys(x.strip() for x in imgs if x.strip())))})
 if not cleaned: raise HTTPException(422,'Add at least one colour/size variant.')
 db.query(ProductVariant).filter(ProductVariant.product_id==p.id).delete(synchronize_session=False)
 db.add_all(ProductVariant(product_id=p.id,**row) for row in cleaned)
 db.flush()
 db.expire(p,['variants'])

@app.post('/api/v1/admin/products',dependencies=[Depends(admin_guard)],status_code=201)
def create_product(payload:ProductInput,db:Session=Depends(db_session)):
 if not db.get(Brand,payload.brand_id):raise HTTPException(404,'Brand not found.')
 if db.scalar(select(Product).where(Product.sku==payload.sku)):raise HTTPException(409,'SKU already exists.')
 data=payload.model_dump(exclude={'images','variants'});images=list(dict.fromkeys(url.strip() for url in payload.images if url.strip()));data['image']=images[0] if images else data['image'];p=Product(**data);db.add(p);db.flush();db.add_all(ProductImage(product_id=p.id,url=url,sort_order=i) for i,url in enumerate(images));variant_rows=payload.variants or [{'colour':payload.colour,'size':sz,'sku':f'{payload.sku}-{sz}','stock':payload.stock if sz=='M' else 0,'images':images} for sz in ['XS','S','M','L','XL','XXL']];save_variants(db,p,variant_rows,images);db.commit();db.refresh(p);return product_json(p)
@app.patch('/api/v1/admin/products/{product_id}',dependencies=[Depends(admin_guard)])
def update_product(product_id:int,payload:dict,db:Session=Depends(db_session)):
 p=db.get(Product,product_id)
 if not p:raise HTTPException(404,'Product not found.')
 allowed={'brand_id','name','category','price','colour','image','images','description','sku','stock','variants','is_active','tag'}
 if set(payload)-allowed:raise HTTPException(422,f"Unsupported fields: {', '.join(sorted(set(payload)-allowed))}")
 if 'stock' in payload and int(payload['stock'])<0:raise HTTPException(422,'Stock cannot be negative.')
 variant_rows=payload.pop('variants',None)
 if 'images' in payload:
  images=payload.pop('images')
  if not isinstance(images,list) or len(images)>12 or any(not isinstance(url,str) or len(url)>1000 for url in images):raise HTTPException(422,'images must be a list of up to 12 image URLs.')
  db.query(ProductImage).filter(ProductImage.product_id==p.id).delete()
  cleaned=list(dict.fromkeys(url.strip() for url in images if url.strip()))
  db.add_all(ProductImage(product_id=p.id,url=url,sort_order=i) for i,url in enumerate(cleaned))
  if cleaned:payload['image']=cleaned[0]
 for k,v in payload.items():setattr(p,k,v)
 if variant_rows is not None:
  if not isinstance(variant_rows,list) or len(variant_rows)>120:raise HTTPException(422,'Provide up to 120 colour/size variants.')
  save_variants(db,p,variant_rows,[x.url for x in sorted(p.gallery_images,key=lambda x:x.sort_order)])
  p.stock=sum(int(v.get('stock',0)) for v in variant_rows)
 db.commit();db.refresh(p);return product_json(p)
@app.get('/api/v1/checkout/config')
def checkout_config(db:Session=Depends(db_session)):
 cod=db.get(AppSetting,'cod_enabled')
 return {'payment_mode':'mock','cod_enabled':bool(cod and cod.value=='true'),'notice':'Development checkout only. No real payment is processed.'}

@app.get('/api/v1/admin/settings',dependencies=[Depends(admin_guard)])
def admin_settings(db:Session=Depends(db_session)):
 cod=db.get(AppSetting,'cod_enabled')
 return {'cod_enabled':bool(cod and cod.value=='true'),'payment_mode':'mock','cod_default':'off'}

@app.patch('/api/v1/admin/settings',dependencies=[Depends(admin_guard)])
def update_admin_settings(payload:dict,db:Session=Depends(db_session)):
 if set(payload)-{'cod_enabled'} or not isinstance(payload.get('cod_enabled'),bool):
  raise HTTPException(422,'Only the boolean cod_enabled setting can be changed.')
 setting=db.get(AppSetting,'cod_enabled')
 if setting is None:
  setting=AppSetting(key='cod_enabled',value='true' if payload['cod_enabled'] else 'false');db.add(setting)
 else: setting.value='true' if payload['cod_enabled'] else 'false'
 db.commit()
 return {'cod_enabled':payload['cod_enabled'],'payment_mode':'mock'}

class OrderServiceDecisionInput(BaseModel):
 status:str=Field(pattern=r'^(approved|rejected|received|refund_pending|refunded|cancelled)$')
 refund_status:str|None=Field(default=None,pattern=r'^(not_applicable|pending|manual_refunded|not_eligible)$')
 admin_note:str=Field(default='',max_length=1000)

class MockPaymentInput(BaseModel):
 outcome:str=Field(pattern=r'^(success|failed|cancelled)$')


@app.post('/api/v1/orders/{order_id}/mock-payment')
def simulate_mock_payment(order_id:int,payload:MockPaymentInput,authorization:str|None=Header(default=None),db:Session=Depends(db_session)):
 order=db.get(CustomerOrder,order_id)
 if not order: raise HTTPException(404,'Order not found.')
 linked_customer=None
 if authorization and authorization.startswith('Bearer '):
  linked_customer=current_customer(authorization=authorization,db=db)
 if linked_customer and order.customer_id!=linked_customer.id: raise HTTPException(403,'This order does not belong to your account.')
 if order.payment_method!='mock_online': raise HTTPException(409,'This order is not using mock online payment.')
 if order.status!='awaiting_payment': raise HTTPException(409,'This order is no longer awaiting payment.')
 if payload.outcome=='success':
  order.payment_status='paid_demo';order.status='confirmed'
  for parcel in order.suborders: parcel.status='confirmed'
 elif payload.outcome=='failed':
  order.payment_status='failed_demo'
 else:
  order.payment_status='cancelled_demo';order.status='cancelled'
  for parcel in order.suborders:
   for item in json.loads(parcel.items_json or '[]'):
    variant=db.get(ProductVariant,item.get('variant_id'))
    if variant: variant.stock+=int(item.get('quantity',0))
    product=db.get(Product,item.get('product_id'))
    if product: product.stock=sum(v.stock for v in product.variants)
   parcel.status='cancelled'
 db.commit();db.refresh(order)
 if payload.outcome=='success': notify_order(order,'Payment confirmed (demo)','Your mock checkout was marked successful. This is a demo payment only; no money was taken.')
 elif payload.outcome=='failed': notify_order(order,'Payment attempt failed','Your mock payment attempt failed. You can return to VEYRA and try again if checkout still permits it.')
 else: notify_order(order,'Checkout cancelled','Your mock checkout was cancelled. No payment was taken.')
 return {'id':order.id,'order_number':order.order_number,'status':order.status,'payment_status':order.payment_status,'notice':'Mock payment simulation only. No money was taken.'}

@app.post('/api/v1/orders',status_code=201)
def create_order(payload:OrderInput,authorization:str|None=Header(default=None),db:Session=Depends(db_session)):
 # Development workflow: validate and reserve exact variants transactionally. Payment remains unconnected.
 try:
  if payload.payment_method not in {'mock_online','cod'}: raise HTTPException(422,'Unsupported payment method.')
  cod_setting=db.get(AppSetting,'cod_enabled')
  if payload.payment_method=='cod' and not (cod_setting and cod_setting.value=='true'): raise HTTPException(403,'Cash on Delivery is currently disabled.')
  ids={line.product_id for line in payload.items}
  products=list(db.scalars(select(Product).where(Product.id.in_(ids),Product.is_active.is_(True))).all())
  by_id={p.id:p for p in products}
  if len(by_id)!=len(ids): raise HTTPException(400,'One or more products are unavailable.')
  resolved=[]; needed=defaultdict(int)
  for line in payload.items:
   p=by_id[line.product_id]
   if line.variant_id is not None:
    variant=db.scalar(select(ProductVariant).where(ProductVariant.id==line.variant_id,ProductVariant.product_id==p.id))
   else:
    variant=db.scalar(select(ProductVariant).where(ProductVariant.product_id==p.id,ProductVariant.colour==line.colour,ProductVariant.size==line.size))
   if not variant: raise HTTPException(409,f'Variant unavailable for {p.name} ({line.colour or "colour"} / {line.size or "size"}).')
   needed[variant.id]+=line.quantity
   resolved.append((line,p,variant))
  variants={v.id:v for v in db.scalars(select(ProductVariant).where(ProductVariant.id.in_(needed.keys()))).all()}
  for vid,qty in needed.items():
   if vid not in variants or variants[vid].stock<qty:
    v=variants.get(vid); raise HTTPException(409,f'Insufficient stock for variant {v.sku if v else vid}.')
  linked_customer=None
  if authorization and authorization.startswith('Bearer '):
   linked_customer=current_customer(authorization=authorization,db=db)
   if linked_customer.email!=payload.customer_email.strip().lower():raise HTTPException(403,'Checkout email must match the signed-in account email.')
  order=CustomerOrder(order_number=f"VYR-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')[-12:]}",customer_id=linked_customer.id if linked_customer else None,customer_email=payload.customer_email.strip().lower(),customer_name=(payload.customer_name or '').strip() or None,phone=(payload.phone or '').strip() or None,shipping_json=json.dumps({'address':payload.shipping_address or '', 'city':payload.city or '', 'state':payload.state or '', 'pincode':payload.pincode or ''}),delivery_method=payload.delivery_method if payload.delivery_method in {'standard','express'} else 'standard',status='confirmed' if payload.payment_method=='cod' else 'awaiting_payment',payment_method=payload.payment_method,payment_status='pending_cod' if payload.payment_method=='cod' else 'unpaid_demo',total=0)
  db.add(order);db.flush();grouped=defaultdict(list);total=0
  for line,p,v in resolved:
   v.stock-=line.quantity
   p.stock=max(0,sum(x.stock for x in p.variants))
   line_total=round(float(p.price)*line.quantity,2);total+=line_total
   grouped[p.brand_id].append({'product_id':p.id,'product_name':p.name,'brand_name':p.brand.name,'variant_id':v.id,'variant_sku':v.sku,'colour':v.colour,'size':v.size,'quantity':line.quantity,'unit_price':float(p.price),'line_total':line_total,'image':(json.loads(v.images_json or '[]') or [p.image])[0]})
  delivery_fee=149.0 if payload.delivery_method=='express' else 0.0
  order.total=round(total+delivery_fee,2)
  for bid,lines in grouped.items():db.add(BrandSuborder(order_id=order.id,brand_id=bid,subtotal=sum(x['line_total'] for x in lines),status='confirmed' if payload.payment_method=='cod' else 'awaiting_payment',items_json=json.dumps(lines)))
  db.commit();db.refresh(order)
  notify_order(order,'Order received', 'We have received your VEYRA order. You can review the order status in your VEYRA account.' + (' Your selected payment method is cash on delivery.' if payload.payment_method=='cod' else ' Checkout payment is still pending; this order confirmation is not proof of payment.'))
  return {'id':order.id,'order_number':order.order_number,'customer_email':order.customer_email,'status':order.status,'payment_status':order.payment_status,'payment_method':order.payment_method,'customer_name':order.customer_name,'phone':order.phone,'shipping':json.loads(order.shipping_json or '{}'),'delivery_method':order.delivery_method,'total':float(order.total),'item_subtotal':round(total,2),'delivery_fee':delivery_fee,'items':[x for ls in grouped.values() for x in ls],'suborders':[{'id':so.id,'brand_name':so.brand.name,'status':so.status,'subtotal':float(so.subtotal),'shipment_tracking_number':so.shipment_tracking_number,'items':json.loads(so.items_json or '[]')} for so in order.suborders],'notice':'Development order created and variant stock reserved. No payment was taken. Cancel the order to release reserved stock.'}
 except Exception:
  db.rollback(); raise

def service_request_json(row:OrderServiceRequest):
 return {'id':row.id,'order_id':row.order_id,'order_number':row.order.order_number if row.order else None,'customer_email':row.order.customer_email if row.order else None,'customer_name':row.order.customer_name if row.order else None,'total':float(row.order.total) if row.order else 0,'order_status':row.order.status if row.order else None,'payment_status':row.order.payment_status if row.order else None,'request_type':row.request_type,'reason':row.reason,'status':row.status,'refund_status':row.refund_status,'admin_note':row.admin_note,'created_at':row.created_at.isoformat() if row.created_at else None,'updated_at':row.updated_at.isoformat() if row.updated_at else None}

def release_order_stock(db:Session,order:CustomerOrder):
 # A cancelled order releases reserved variant stock once only.
 if order.status=='cancelled': return
 for parcel in order.suborders:
  if parcel.status!='cancelled':
   for item in json.loads(parcel.items_json or '[]'):
    variant=db.get(ProductVariant,item.get('variant_id'))
    if variant: variant.stock += int(item.get('quantity',0))
    product=db.get(Product,item.get('product_id'))
    if product: product.stock=sum(v.stock for v in product.variants)
   parcel.status='cancelled'
 order.status='cancelled'

@app.post('/api/v1/account/orders/{order_id}/service-requests',status_code=201)
def create_order_service_request(order_id:int,payload:OrderServiceRequestInput,customer:Customer=Depends(current_customer),db:Session=Depends(db_session)):
 order=db.get(CustomerOrder,order_id)
 if not order or order.customer_id!=customer.id: raise HTTPException(404,'Order not found in your account.')
 if payload.request_type=='cancellation':
  if order.status not in {'awaiting_payment','confirmed','processing'}: raise HTTPException(409,'Cancellation requests are only available before dispatch. Contact support if the parcel has already shipped.')
 else:
  if order.status!='delivered': raise HTTPException(409,'Return requests are available after the order is marked delivered.')
 active=db.scalar(select(OrderServiceRequest).where(OrderServiceRequest.order_id==order.id,OrderServiceRequest.request_type==payload.request_type,OrderServiceRequest.status.in_(['requested','approved','received','refund_pending'])))
 if active: raise HTTPException(409,'There is already an open request of this type for this order.')
 row=OrderServiceRequest(order_id=order.id,customer_id=customer.id,request_type=payload.request_type,reason=payload.reason.strip(),status='requested',refund_status='pending' if order.payment_status in {'paid_demo','paid'} else 'not_applicable')
 db.add(row);db.commit();db.refresh(row)
 notify_order(order,f'{payload.request_type.title()} request received',f'We received your {payload.request_type} request for order {order.order_number}. Our team will review it. Reason: {row.reason}')
 return service_request_json(row)

@app.get('/api/v1/account/service-requests')
def customer_service_requests(customer:Customer=Depends(current_customer),db:Session=Depends(db_session)):
 rows=list(db.scalars(select(OrderServiceRequest).where(OrderServiceRequest.customer_id==customer.id).order_by(OrderServiceRequest.id.desc()).limit(100)).all())
 return [service_request_json(row) for row in rows]

@app.get('/api/v1/admin/returns',dependencies=[Depends(admin_guard)])
def admin_service_requests(db:Session=Depends(db_session)):
 rows=list(db.scalars(select(OrderServiceRequest).order_by(OrderServiceRequest.id.desc()).limit(300)).all())
 return [service_request_json(row) for row in rows]

@app.patch('/api/v1/admin/returns/{request_id}',dependencies=[Depends(admin_guard)])
def admin_update_service_request(request_id:int,payload:OrderServiceDecisionInput,db:Session=Depends(db_session)):
 row=db.get(OrderServiceRequest,request_id)
 if not row: raise HTTPException(404,'Return/cancellation request not found.')
 order=row.order
 if row.status in {'rejected','cancelled','refunded'}: raise HTTPException(409,'This request is already closed.')
 status=payload.status
 if row.request_type=='cancellation':
  if status=='approved':
   if order.status not in {'awaiting_payment','confirmed','processing'}: raise HTTPException(409,'The order has already moved beyond the cancellation window.')
   release_order_stock(db,order)
   row.refund_status='pending' if order.payment_status in {'paid_demo','paid'} else 'not_applicable'
  elif status in {'received','refund_pending','refunded'}: raise HTTPException(422,'Cancellation requests can be approved, rejected or closed only.')
 else:
  if status=='approved' and order.status!='delivered': raise HTTPException(409,'Only delivered orders can have an approved return.')
  if status=='received' and row.status not in {'approved','received'}: raise HTTPException(409,'Approve the return before marking it received.')
  if status in {'refund_pending','refunded'} and order.payment_status not in {'paid_demo','paid'}:
   raise HTTPException(409,'No captured online payment is recorded. Do not mark a refund for an unpaid order.')
  if status=='refund_pending' and row.status not in {'approved','received','refund_pending'}:
   raise HTTPException(409,'Approve the return and mark it received before recording a refund as pending.')
  if status=='refunded' and row.status!='refund_pending':
   raise HTTPException(409,'Mark the refund pending first, then record the manual refund after completing it with the payment provider.')
 if payload.refund_status:
  if payload.refund_status in {'pending','manual_refunded'} and order.payment_status not in {'paid_demo','paid'}: raise HTTPException(409,'Order has no recorded paid status; refund cannot be marked pending or refunded.')
  row.refund_status=payload.refund_status
 elif status=='refund_pending': row.refund_status='pending'
 elif status=='refunded': row.refund_status='manual_refunded'
 row.status=status;row.admin_note=payload.admin_note.strip();row.updated_at=datetime.now(timezone.utc)
 db.commit();db.refresh(row)
 note=f'Admin note: {row.admin_note}' if row.admin_note else ''
 detail=f"Your {row.request_type} request for order {order.order_number} is now {row.status.replace('_',' ')}. Refund status: {row.refund_status.replace('_',' ')}. {note}".strip()
 notify_order(order,f'{row.request_type.title()} request updated',detail)
 return service_request_json(row)

@app.get('/api/v1/admin/orders',dependencies=[Depends(admin_guard)])
def admin_orders(db:Session=Depends(db_session)):
 orders=list(db.scalars(select(CustomerOrder).order_by(CustomerOrder.id.desc()).limit(200)).all())
 return [{'id':o.id,'order_number':o.order_number,'customer_email':o.customer_email,'status':o.status,'payment_status':o.payment_status,'payment_method':o.payment_method,'customer_name':o.customer_name,'phone':o.phone,'shipping':json.loads(o.shipping_json or '{}'),'delivery_method':o.delivery_method,'total':float(o.total),'created_at':o.created_at.isoformat() if o.created_at else None,'suborders':[{'id':so.id,'brand_id':so.brand_id,'brand':so.brand.name,'status':so.status,'subtotal':float(so.subtotal),'tracking':so.shipment_tracking_number,'items':json.loads(so.items_json or '[]')} for so in o.suborders]} for o in orders]

@app.patch('/api/v1/admin/orders/{order_id}',dependencies=[Depends(admin_guard)])
def admin_update_order(order_id:int,payload:dict,db:Session=Depends(db_session)):
 allowed={'status'}
 if set(payload)-allowed:raise HTTPException(422,'Only order status may be changed here.')
 status=payload.get('status')
 if status not in {'awaiting_payment','confirmed','processing','dispatched','delivered','cancelled'}:raise HTTPException(422,'Unsupported order status.')
 try:
  order=db.get(CustomerOrder,order_id)
  if not order:raise HTTPException(404,'Order not found.')
  if order.status=='cancelled' and status!='cancelled':raise HTTPException(409,'Cancelled orders cannot be reopened; create a new order.')
  if status=='cancelled' and order.status!='cancelled':
   for so in order.suborders:
    if so.status!='cancelled':
     for item in json.loads(so.items_json or '[]'):
      variant=db.get(ProductVariant,item.get('variant_id'))
      if variant:variant.stock+=int(item.get('quantity',0))
      product=db.get(Product,item.get('product_id'))
      if product:product.stock=sum(v.stock for v in product.variants)
    so.status='cancelled'
  elif status in {'confirmed','processing','dispatched','delivered'} and order.status=='awaiting_payment':
   # Manual admin confirmation only; this is not proof of a payment-provider webhook.
   for so in order.suborders:so.status=status
  else:
   for so in order.suborders:
    if so.status!='cancelled':so.status=status
  previous_status=order.status
  order.status=status;db.commit();db.refresh(order)
  if previous_status!=status:
   notify_order(order,f'Order {status.replace("_"," ").title()}',f'Your VEYRA order {order.order_number} status changed from {previous_status.replace("_"," ")} to {status.replace("_"," ")}.')
  return {'id':order.id,'order_number':order.order_number,'status':order.status,'payment_status':order.payment_status}
 except Exception:
  db.rollback();raise

@app.patch('/api/v1/admin/suborders/{suborder_id}',dependencies=[Depends(admin_guard)])
def admin_update_suborder(suborder_id:int,payload:dict,db:Session=Depends(db_session)):
 if set(payload)-{'status','tracking'}:raise HTTPException(422,'Unsupported parcel fields.')
 so=db.get(BrandSuborder,suborder_id)
 if not so:raise HTTPException(404,'Brand parcel not found.')
 status=payload.get('status',so.status)
 if status not in {'awaiting_payment','confirmed','processing','dispatched','delivered','cancelled'}:raise HTTPException(422,'Unsupported parcel status.')
 tracking=payload.get('tracking',so.shipment_tracking_number)
 if tracking is not None and len(str(tracking))>120:raise HTTPException(422,'Tracking reference is too long.')
 try:
  if status=='cancelled' and so.status!='cancelled':
   for item in json.loads(so.items_json or '[]'):
    variant=db.get(ProductVariant,item.get('variant_id'))
    if variant:variant.stock+=int(item.get('quantity',0))
    product=db.get(Product,item.get('product_id'))
    if product:product.stock=sum(v.stock for v in product.variants)
  previous_status=so.status;previous_tracking=so.shipment_tracking_number
  so.status=status;so.shipment_tracking_number=tracking
  # Keep the parent order status in sync with independently fulfilled brand parcels.
  parcel_statuses=[parcel.status for parcel in so.order.suborders]
  active_statuses=[value for value in parcel_statuses if value!='cancelled']
  if not active_statuses:
   so.order.status='cancelled'
  elif all(value=='delivered' for value in active_statuses):
   so.order.status='delivered'
  elif any(value=='dispatched' for value in active_statuses):
   so.order.status='dispatched'
  elif any(value=='processing' for value in active_statuses):
   so.order.status='processing'
  elif any(value=='confirmed' for value in active_statuses):
   so.order.status='confirmed'
  else:
   so.order.status='awaiting_payment'
  db.commit();db.refresh(so)
  if previous_status!=so.status or previous_tracking!=so.shipment_tracking_number:
   details=f'{so.brand.name} parcel status: {so.status.replace("_"," ").title()}.'
   if so.shipment_tracking_number: details+=f' Tracking reference: {so.shipment_tracking_number}.'
   notify_order(so.order,'Shipment update',f'Your VEYRA order {so.order.order_number} has a parcel update. {details}')
  return {'id':so.id,'order_id':so.order_id,'order_status':so.order.status,'brand':so.brand.name,'status':so.status,'tracking':so.shipment_tracking_number}
 except Exception:
  db.rollback();raise

@app.get('/api/v1/admin/reports',dependencies=[Depends(admin_guard)])
def admin_reports(db:Session=Depends(db_session)):
 products=list(db.scalars(select(Product)).all())
 orders=list(db.scalars(select(CustomerOrder)).all())
 return {'products_total':len(products),'products_published':sum(1 for p in products if p.is_active),'inventory_units':sum(max(0,int(p.stock or 0)) for p in products),'low_stock_products':[{'id':p.id,'name':p.name,'sku':p.sku,'stock':int(p.stock or 0)} for p in products if p.is_active and int(p.stock or 0)<=5],'orders_total':len(orders),'orders_awaiting_payment':sum(1 for o in orders if o.status=='awaiting_payment'),'orders_cancelled':sum(1 for o in orders if o.status=='cancelled'),'delivered_order_value':round(sum(float(o.total) for o in orders if o.status=='delivered'),2),'note':'Development report. Orders awaiting payment are not recognized as revenue; payment gateway reconciliation is not connected.'}
