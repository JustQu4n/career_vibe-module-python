def greet(name: str = "world") -> str:
    return f"Hello, {name}!"


def main():
    print(greet())


if __name__ == "__main__":
    main()
