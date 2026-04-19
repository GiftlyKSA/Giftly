from utils.database.database import Base
from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship


class City(Base):
    __tablename__ = "cities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)

    def __str__(self):
        return self.name

    icon = Column(String, nullable=True)
    active = Column(Boolean, default=True)

    # Relationship to orders
    orders = relationship("Order", back_populates="city")
