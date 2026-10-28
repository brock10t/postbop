import sys

from .application import PostBopApplication

def main():
    app = PostBopApplication()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())