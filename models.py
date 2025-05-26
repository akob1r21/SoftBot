from sqlalchemy import Column, Integer , BigInteger , String,  DateTime
from db import Base 
from datetime import datetime



class Student(Base):
    __tablename__ = 'new_students'    

    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger)
    fullname = Column(String(150), nullable=False)
    phone_number = Column(String(15), nullable=True)
    second_phone_number = Column(String(15), nullable=True)
    course_name = Column(String(50), nullable=False)
    registration_date = Column(DateTime, default=datetime.now)




class Admin(Base):
    __tablename__ = 'admins'

    id = Column(Integer, primary_key=True)
    admin_tg = Column(BigInteger, unique=True)
    username = Column(String(70), unique=True, nullable=False)
    last_activity = Column(DateTime)



class Users(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    user_tg = Column(BigInteger, unique=True)
    username = Column(String(70), unique=True, nullable=True)
    registration_date = Column(DateTime, default=datetime.now)



# if __name__ == "__main__":
#     Base.metadata.create_all(engine)


