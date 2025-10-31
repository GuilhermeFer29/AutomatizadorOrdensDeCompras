"""Tests for authentication endpoints."""

import pytest
from fastapi.testclient import TestClient


def test_register_user(client: TestClient):
    """Test user registration."""
    response = client.post(
        "/auth/register",
        json={
            "email": "test@example.com",
            "password": "secure_password_123",
            "full_name": "Test User"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data


def test_register_duplicate_email(client: TestClient):
    """Test registration with duplicate email."""
    # First registration
    client.post(
        "/auth/register",
        json={
            "email": "duplicate@example.com",
            "password": "password123",
            "full_name": "First User"
        }
    )
    
    # Second registration with same email
    response = client.post(
        "/auth/register",
        json={
            "email": "duplicate@example.com",
            "password": "password456",
            "full_name": "Second User"
        }
    )
    assert response.status_code == 400
    assert "já cadastrado" in response.json()["detail"]


def test_login_success(client: TestClient):
    """Test successful login."""
    # Register user first
    client.post(
        "/auth/register",
        json={
            "email": "login@example.com",
            "password": "test_password",
            "full_name": "Login Test"
        }
    )
    
    # Login using form data (OAuth2PasswordRequestForm expects form data)
    response = client.post(
        "/auth/login",
        data={
            "username": "login@example.com",
            "password": "test_password"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_credentials(client: TestClient):
    """Test login with invalid credentials."""
    response = client.post(
        "/auth/login",
        data={
            "username": "nonexistent@example.com",
            "password": "wrong_password"
        }
    )
    assert response.status_code == 401
    assert "inválidos" in response.json()["detail"]


def test_login_wrong_password(client: TestClient):
    """Test login with wrong password."""
    # Register user
    client.post(
        "/auth/register",
        json={
            "email": "wrongpass@example.com",
            "password": "correct_password",
            "full_name": "Wrong Pass Test"
        }
    )
    
    # Try login with wrong password using form data
    response = client.post(
        "/auth/login",
        data={
            "username": "wrongpass@example.com",
            "password": "wrong_password"
        }
    )
    assert response.status_code == 401
    assert "inválidos" in response.json()["detail"]
