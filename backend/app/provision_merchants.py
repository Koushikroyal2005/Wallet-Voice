"""Operator CLI: emits newly generated demo merchant credentials once. Store securely."""
from .db import SessionLocal
from .merchants import provision
def main():
    with SessionLocal() as db:
        credentials=[(ident,provision(db,ident,name)) for ident,name in [('demo-railway','Demo Railway'),('demo-food','Demo Kitchen')]]
        db.commit()
    for ident,key in credentials:print(f'{ident}: {key}')
if __name__=='__main__':main()
