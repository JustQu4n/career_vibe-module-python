from ai_project import main


def test_greet():
    assert main.greet("Bob") == "Hello, Bob!"
