"""Unit tests for core domain entities."""

from src.core.entities.user import User


class TestUserEntity:
    """Test the User domain entity."""

    def test_create_valid_user(self):
        """Should create a valid user with required fields."""
        user = User(
            id=1,
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com"
        )
        
        assert user.id == 1
        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert user.email == "john.doe@example.com"
        assert user.phone is None
        assert user.address is None

    def test_create_user_with_optional_fields(self):
        """Should create a user with all optional fields."""
        user = User(
            id=2,
            first_name="Jane",
            last_name="Smith",
            email="jane.smith@example.com",
            phone="+1-555-123-4567",
            address="123 Main St, Anytown, USA"
        )
        
        assert user.phone == "+1-555-123-4567"
        assert user.address == "123 Main St, Anytown, USA"

    def test_user_validation_invalid_email(self):
        """Should allow any email format (no validation constraints in entity)."""
        # The User entity doesn't enforce email validation
        user = User(
            id=1,
            first_name="John",
            last_name="Doe",
            email="not-a-valid-email"  # This should be allowed
        )
        assert user.email == "not-a-valid-email"

    def test_user_validation_empty_names(self):
        """Should allow empty first or last names (no validation constraints in entity)."""
        # The User entity doesn't enforce name validation
        user = User(
            id=1,
            first_name="",  # Empty names should be allowed
            last_name="",
            email="test@example.com"
        )
        assert user.first_name == ""
        assert user.last_name == ""

    def test_user_equality(self):
        """Should compare users by their attributes."""
        user1 = User(
            id=1,
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com"
        )
        
        user2 = User(
            id=1,
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com"
        )
        
        user3 = User(
            id=2,
            first_name="Jane",
            last_name="Smith",
            email="jane.smith@example.com"
        )
        
        assert user1 == user2
        assert user1 != user3

    def test_user_representation(self):
        """Should have a meaningful string representation."""
        user = User(
            id=1,
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com"
        )
        
        user_str = str(user)
        assert "John" in user_str
        assert "Doe" in user_str
        assert "john.doe@example.com" in user_str