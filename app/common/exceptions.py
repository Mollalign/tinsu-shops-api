from fastapi import HTTPException, status


class AppException(HTTPException):
    """Base application exception that maps to HTTP responses."""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(
            status_code=status_code,
            detail={"code": code, "message": message},
        )


# --- 400 Bad Request ---
class InvalidCredentialsError(AppException):
    def __init__(self, message: str = "Invalid credentials."):
        super().__init__(status.HTTP_401_UNAUTHORIZED, "INVALID_CREDENTIALS", message)


class InsufficientStockError(AppException):
    def __init__(self, product_name: str, available: int):
        super().__init__(
            status.HTTP_400_BAD_REQUEST,
            "INSUFFICIENT_STOCK",
            f"'{product_name}' has only {available} item(s) available.",
        )


class NegativeStockError(AppException):
    def __init__(self, product_name: str):
        super().__init__(
            status.HTTP_400_BAD_REQUEST,
            "NEGATIVE_STOCK",
            f"Adjustment would result in negative stock for '{product_name}'.",
        )


class InactiveProductError(AppException):
    def __init__(self, product_name: str):
        super().__init__(
            status.HTTP_400_BAD_REQUEST,
            "INACTIVE_PRODUCT",
            f"Product '{product_name}' is not active.",
        )


class InvalidPaymentMethodError(AppException):
    def __init__(self, method: str):
        super().__init__(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_PAYMENT_METHOD",
            f"Payment method '{method}' is not valid.",
        )


class EmptySaleError(AppException):
    def __init__(self):
        super().__init__(
            status.HTTP_400_BAD_REQUEST,
            "EMPTY_SALE",
            "A sale must contain at least one item.",
        )


class InvalidPinError(AppException):
    def __init__(self):
        super().__init__(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_PIN",
            "PIN must be at least 4 digits.",
        )


# --- 401 Unauthorized ---
class NotAuthenticatedError(AppException):
    def __init__(self):
        super().__init__(
            status.HTTP_401_UNAUTHORIZED,
            "NOT_AUTHENTICATED",
            "Authentication is required.",
        )


class TokenExpiredError(AppException):
    def __init__(self):
        super().__init__(
            status.HTTP_401_UNAUTHORIZED,
            "TOKEN_EXPIRED",
            "Your session has expired. Please log in again.",
        )


class InvalidTokenError(AppException):
    def __init__(self):
        super().__init__(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_TOKEN",
            "Invalid or malformed token.",
        )


# --- 403 Forbidden ---
class UnauthorizedShopAccessError(AppException):
    def __init__(self):
        super().__init__(
            status.HTTP_403_FORBIDDEN,
            "UNAUTHORIZED_SHOP_ACCESS",
            "You do not have access to this shop.",
        )


class OwnerOnlyError(AppException):
    def __init__(self):
        super().__init__(
            status.HTTP_403_FORBIDDEN,
            "OWNER_ONLY",
            "This action requires owner privileges.",
        )


class InactiveAccountError(AppException):
    def __init__(self):
        super().__init__(
            status.HTTP_403_FORBIDDEN,
            "INACTIVE_ACCOUNT",
            "This account has been disabled.",
        )


# --- 404 Not Found ---
class ShopNotFoundError(AppException):
    def __init__(self):
        super().__init__(status.HTTP_404_NOT_FOUND, "SHOP_NOT_FOUND", "Shop not found.")


class ProductNotFoundError(AppException):
    def __init__(self):
        super().__init__(status.HTTP_404_NOT_FOUND, "PRODUCT_NOT_FOUND", "Product not found.")


class WorkerNotFoundError(AppException):
    def __init__(self):
        super().__init__(status.HTTP_404_NOT_FOUND, "WORKER_NOT_FOUND", "Worker not found.")


class SaleNotFoundError(AppException):
    def __init__(self):
        super().__init__(status.HTTP_404_NOT_FOUND, "SALE_NOT_FOUND", "Sale not found.")


class OwnerNotFoundError(AppException):
    def __init__(self):
        super().__init__(status.HTTP_404_NOT_FOUND, "OWNER_NOT_FOUND", "Owner not found.")


# --- 409 Conflict ---
class PhoneAlreadyExistsError(AppException):
    def __init__(self):
        super().__init__(
            status.HTTP_409_CONFLICT,
            "PHONE_ALREADY_EXISTS",
            "This phone number is already registered.",
        )


class DuplicateCategoryNameError(AppException):
    def __init__(self, name: str = ""):
        super().__init__(
            status.HTTP_409_CONFLICT,
            "DUPLICATE_CATEGORY_NAME",
            f"A category named '{name}' already exists in this shop.",
        )


# --- 404 Not Found (categories) ---
class CategoryNotFoundError(AppException):
    def __init__(self):
        super().__init__(
            status.HTTP_404_NOT_FOUND,
            "CATEGORY_NOT_FOUND",
            "Category not found.",
        )
