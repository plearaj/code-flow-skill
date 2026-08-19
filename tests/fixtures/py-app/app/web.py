"""HTTP surface."""
from app.service import authenticate

app = object()


@app.route("/login", methods=["POST"])
def login_view(request):
    """Handle POST /login."""
    return authenticate(request.form["id"], request.form["password"])


def main():
    """Run the development server."""
    return login_view(None)


if __name__ == "__main__":
    main()
