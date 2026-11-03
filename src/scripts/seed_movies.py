from decimal import Decimal

from sqlalchemy import select

from src.database import SessionLocal
from src.models import Certification, Director, Genre, Movie, Star

MOVIES = [
    {
        "name": "Inception", "year": 2010, "time": 148, "imdb": 8.8,
        "votes": 2400000, "price": "9.99", "certification": "PG-13",
        "description": "A thief who steals secrets through dreams gets a chance to erase his past.",
        "genres": ["Sci-Fi", "Action"],
        "directors": ["Christopher Nolan"],
        "stars": ["Leonardo DiCaprio", "Elliot Page"],
    },
    {
        "name": "The Dark Knight", "year": 2008, "time": 152, "imdb": 9.0,
        "votes": 2700000, "price": "12.00", "certification": "PG-13",
        "description": "Batman faces the Joker, a criminal mastermind who spreads chaos in Gotham.",
        "genres": ["Action", "Crime", "Drama"],
        "directors": ["Christopher Nolan"],
        "stars": ["Christian Bale", "Heath Ledger"],
    },
    {
        "name": "Interstellar", "year": 2014, "time": 169, "imdb": 8.7,
        "votes": 2200000, "price": "10.50", "certification": "PG-13",
        "description": "Explorers travel through a wormhole in search of a new home for humanity.",
        "genres": ["Sci-Fi", "Drama", "Adventure"],
        "directors": ["Christopher Nolan"],
        "stars": ["Matthew McConaughey", "Anne Hathaway"],
    },
    {
        "name": "Pulp Fiction", "year": 1994, "time": 154, "imdb": 8.9,
        "votes": 2100000, "price": "7.50", "certification": "R",
        "description": "Intertwined stories of criminals, a boxer and two hitmen in Los Angeles.",
        "genres": ["Crime", "Drama"],
        "directors": ["Quentin Tarantino"],
        "stars": ["John Travolta", "Samuel L. Jackson"],
    },
    {
        "name": "The Matrix", "year": 1999, "time": 136, "imdb": 8.7,
        "votes": 2000000, "price": "8.00", "certification": "R",
        "description": "A hacker discovers that reality is a simulation controlled by machines.",
        "genres": ["Sci-Fi", "Action"],
        "directors": ["Lana Wachowski", "Lilly Wachowski"],
        "stars": ["Keanu Reeves", "Carrie-Anne Moss"],
    },
    {
        "name": "Forrest Gump", "year": 1994, "time": 142, "imdb": 8.8,
        "votes": 2300000, "price": "6.99", "certification": "PG-13",
        "description": "A kind man with a low IQ accidentally takes part in key moments of American history.",
        "genres": ["Drama", "Romance"],
        "directors": ["Robert Zemeckis"],
        "stars": ["Tom Hanks", "Robin Wright"],
    },
    {
        "name": "Gladiator", "year": 2000, "time": 155, "imdb": 8.5,
        "votes": 1600000, "price": "8.50", "certification": "R",
        "description": "A betrayed Roman general becomes a gladiator and seeks revenge.",
        "genres": ["Action", "Drama", "Adventure"],
        "directors": ["Ridley Scott"],
        "stars": ["Russell Crowe", "Joaquin Phoenix"],
    },
    {
        "name": "Toy Story", "year": 1995, "time": 81, "imdb": 8.3,
        "votes": 1100000, "price": "5.99", "certification": "G",
        "description": "A cowboy doll feels threatened when a new space ranger toy arrives.",
        "genres": ["Animation", "Adventure", "Comedy"],
        "directors": ["John Lasseter"],
        "stars": ["Tom Hanks", "Tim Allen"],
    },
]


def get_or_create(db, model, name: str):
    obj = db.scalar(select(model).where(model.name == name))
    if obj is None:
        obj = model(name=name)
        db.add(obj)
        db.flush()
    return obj


def seed_movies() -> None:
    db = SessionLocal()
    try:
        created = 0
        for data in MOVIES:
            exists = db.scalar(
                select(Movie).where(
                    Movie.name == data["name"],
                    Movie.year == data["year"],
                    Movie.time == data["time"],
                )
            )
            if exists:
                continue

            movie = Movie(
                name=data["name"],
                year=data["year"],
                time=data["time"],
                imdb=data["imdb"],
                votes=data["votes"],
                description=data["description"],
                price=Decimal(data["price"]),
                certification_id=get_or_create(
                    db, Certification, data["certification"]
                ).id,
            )
            movie.genres = [get_or_create(db, Genre, n) for n in data["genres"]]
            movie.directors = [get_or_create(db, Director, n) for n in data["directors"]]
            movie.stars = [get_or_create(db, Star, n) for n in data["stars"]]
            db.add(movie)
            created += 1

        db.commit()
        print(f"Done. Added {created} new movies.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_movies()
