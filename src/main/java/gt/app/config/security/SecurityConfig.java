package gt.app.config.security;

import gt.app.config.Constants;
import io.quarkus.security.Authenticated;
import io.quarkus.security.identity.SecurityIdentity;
import io.quarkus.security.spi.runtime.AuthorizationController;
import jakarta.annotation.Priority;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Produces;
import jakarta.inject.Inject;
import jakarta.inject.Singleton;
import jakarta.ws.rs.Priorities;
import jakarta.ws.rs.container.ContainerRequestContext;
import jakarta.ws.rs.container.ContainerRequestFilter;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.ext.Provider;
import org.eclipse.microprofile.config.inject.ConfigProperty;

import java.io.IOException;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

@ApplicationScoped
public class SecurityConfig {

     static final List<String> AUTH_WHITELIST = Arrays.asList(
        "/swagger-resources",
        "/v3/api-docs",
        "/webjars",
        "/static",
        "/error",
        "/swagger-ui",
        "/swagger-ui.html",
        "/signup",
        "/h2-console",
        "/debug",
        "/" // landing page is allowed for all
    );

//    @Produces
//    @Singleton
//    public PasswordEncoder passwordEncoder() {
//        return new BCryptPasswordEncoder();
//    }
//
//    // PasswordEncoder interface
//    public interface PasswordEncoder {
//        String encode(CharSequence rawPassword);
//        boolean matches(CharSequence rawPassword, String encodedPassword);
//    }
//
//    // BCrypt implementation
//    public static class BCryptPasswordEncoder implements PasswordEncoder {
//        @Override
//        public String encode(CharSequence rawPassword) {
//            return BCrypt
//        }
//
//        @Override
//        public boolean matches(CharSequence rawPassword, String encodedPassword) {
//            return BCrypt.checkpw(rawPassword.toString(), encodedPassword);
//        }
//    }
}

// JAX-RS Security Filter for path-based authorization
@Provider
@Priority(Priorities.AUTHORIZATION)
class SecurityFilter implements ContainerRequestFilter {

    @Inject
    SecurityIdentity securityIdentity;

    @Override
    public void filter(ContainerRequestContext requestContext) throws IOException {
        String path = requestContext.getUriInfo().getPath();

        // Skip authentication check for whitelisted paths
        if (isWhitelisted(path)) {
            return;
        }

        // Check if user is authenticated (except for whitelisted paths)
        if (securityIdentity.isAnonymous()) {
            requestContext.abortWith(Response.status(Response.Status.UNAUTHORIZED).build());
            return;
        }

        // Role-based authorization
        if (path.startsWith("/admin/") && !securityIdentity.hasRole(Constants.ROLE_ADMIN)) {
            requestContext.abortWith(Response.status(Response.Status.FORBIDDEN).build());
            return;
        }

        if (path.startsWith("/user/") && !securityIdentity.hasRole(Constants.ROLE_USER)) {
            requestContext.abortWith(Response.status(Response.Status.FORBIDDEN).build());
        }
    }

    private boolean isWhitelisted(String path) {
        return SecurityConfig.AUTH_WHITELIST.stream().anyMatch(path::startsWith);
    }
}

// Disable authorization for development endpoints (optional)
@Singleton
class DevelopmentAuthorizationController extends AuthorizationController {
    @ConfigProperty(name = "quarkus.security.enable-authorization", defaultValue = "true")
    boolean authorizationEnabled;

    @Override
    public boolean isAuthorizationEnabled() {
        return authorizationEnabled;
    }
}

// Method security using annotations
// In your REST endpoints or service classes, use these annotations:
// - @Authenticated - for endpoints requiring authentication
// - @RolesAllowed({"ROLE_ADMIN"}) - for role-based access
