import os, csv

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

if not os.getenv('DATABASE_URL'):
    raise RuntimeError('DATABASE_URL is not defined')

DB=os.getenv('DATABASE_URL')

engine = create_engine(DB)
db = scoped_session(sessionmaker(bind=engine))

# TODO
#  - let the user choose what to do in case of duplicate insert ( ignore and keep going, or abort )
#  - use a flag to handle the header presence or absence
#
# Assumes there is a header line
def main():

    f = open('books.csv')

    reader = csv.reader(f)

    print("I'll skip the first line of the file, as I assume it is a header line")

    n=-1
    for isbn, title, author, year in reader:

        n+=1

        # Skip header line
        if n==0:
            continue

        try:
            db.execute('insert into books(isbn, title, author, year) values(:isbn, :title, :author, :year)', {'isbn':isbn, 'title':title, 'author':author, 'year':int(year)})
        except:
            # Catches all, in particular duplicate errors
            raise RuntimeError('Error while inserting')


        print(f'{n} books added so far') if n % 10 ==1 else None

    db.commit()

    print(f'{n} books were added')

if __name__=='__main__':
    main()

