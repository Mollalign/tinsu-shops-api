import enum


class UserRole(str, enum.Enum):
    OWNER = "owner"
    WORKER = "worker"


class InventoryMovementType(str, enum.Enum):
    INITIAL = "INITIAL"
    RESTOCK = "RESTOCK"
    SALE = "SALE"
    ADJUSTMENT = "ADJUSTMENT"
    RETURN = "RETURN"


class PaymentMethod(str, enum.Enum):
    CASH = "CASH"
    TELEBIRR = "TELEBIRR"
    CBE_BIRR = "CBE_BIRR"
    OTHER = "OTHER"


class ActorType(str, enum.Enum):
    OWNER = "OWNER"
    WORKER = "WORKER"
