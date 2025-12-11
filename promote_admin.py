from app.database import SessionLocal
from app.models import User

def make_admin(username: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"User '{username}' not found.")
            return
        user.role = "admin"
        db.commit()
        print(f"User '{username}' is now an admin.")
    finally:
        db.close()

if __name__ == "__main__":
    target = input("Username to promote to admin: ").strip()
    make_admin(target)
