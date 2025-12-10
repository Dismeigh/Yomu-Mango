from app.database import SessionLocal, engine
from app.models import Base, Manga, Chapter

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Check if anything already exists
        if db.query(Manga).first():
            print("Database already has data, skipping seed.")
            return

        manga = Manga(
            title="Example Manga",
            alt_title="Demo Series",
            description="This is an example manga entry used to test the index.",
            status="ongoing",
            content_rating="safe",
            type="manga",
            cover_image_url=None,  # or use your own image URL if you have rights
        )
        db.add(manga)
        db.flush()  # so manga.id is set

        ch1 = Chapter(
            manga_id=manga.id,
            number=1,
            title="Chapter One",
            language="en",
            external_url="https://example.com/manga/example-manga/chapter-1",
            source_name="ExampleSource",
        )
        ch2 = Chapter(
            manga_id=manga.id,
            number=2,
            title="Chapter Two",
            language="en",
            external_url="https://example.com/manga/example-manga/chapter-2",
            source_name="ExampleSource",
        )

        db.add_all([ch1, ch2])
        db.commit()
        print("Seed data inserted.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
