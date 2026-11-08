Why this endpoint has the token in the body instead of the header ?

  /auth/refresh:

The reason is that refresh tokens are often handled differently from access tokens, especially when using HTTP-only cookies.

In your OpenAPI definition, the `/auth/refresh` endpoint supports two ways of receiving the refresh token.

## 1. Refresh token in the request body

http

```http
POST /auth/refresh
Content-Type: application/json

{
  "refreshToken": "your-refresh-token"
}
```

This approach is useful when:

- Your frontend explicitly manages the refresh token.
- You're building a mobile application.
- You're using a client that cannot easily manage HTTP-only cookies.

However, storing refresh tokens in JavaScript-accessible storage (such as `localStorage`) increases the risk of token theft through XSS attacks.

## 2. Refresh token in an HTTP-only cookie

Alternatively, the browser automatically sends the cookie:

http

```http
POST /auth/refresh
Cookie: refreshToken=your-refresh-token
```

The backend reads the refresh token from the cookie.

This is generally preferable for browser-based applications because:

- JavaScript cannot directly read HTTP-only cookies.
- It reduces the risk of refresh-token theft through XSS.
- The frontend doesn't need to manually manage the refresh token.

You should also implement appropriate `Secure`, `SameSite`, and CSRF protections.

## 3. Why is there no Authorization header?

You might expect something like:

http

```http
POST /auth/refresh
Authorization: Bearer <refresh-token>
```

But this isn't necessarily the best design.

The `Authorization: Bearer` header is conventionally used to send access tokens when accessing protected resources.

Refresh tokens have a different purpose: obtaining a new access token.

Keeping them separate makes the authentication flow easier to reason about.

## 4. What does `security: []` mean?

This is particularly important in your OpenAPI definition:

yaml

```yaml
security: []
```

It means this endpoint does not inherit the global security requirements defined in your OpenAPI document.

That's expected because the refresh endpoint must be accessible even when the access token has expired.

The backend independently validates the refresh token, either from:

- The request body.
- An HTTP-only cookie.

## My recommendation

For a browser-based application, I'd recommend:

| Endpoint | Token location |
| --- | --- |
| `POST /auth/login` | Credentials in body |
| `POST /auth/refresh` | HTTP-only cookie |
| `POST /auth/logout` | HTTP-only cookie |
| Protected endpoints | `Authorization: Bearer <accessToken>` |

I'd also modify your OpenAPI definition to explicitly document the cookie-based approach, rather than making the body token appear like the primary mechanism.

In short: The refresh token is in the body because your API supports clients that explicitly supply it. It doesn't have to be there; for browser applications, an HTTP-only cookie is generally a better approach.

---

Passwords need slow hashes (Argon2/Bcrypt): Humans create terrible, predictable passwords. passlib uses algorithms that are intentionally slow and computationally expensive to prevent attackers from brute-forcing millions of guesses a second if your database leaks.

Tokens need fast hashes (SHA-256): Your refresh tokens are randomly generated, cryptographically secure, high-entropy strings (via JWT). An attacker cannot brute-force or guess a JWT. Because the token itself is already unguessable, you don't need a "slow" hash. You just need a one-way mathematical scramble so the raw token isn't sitting in plaintext in your database.
