package gt.app.config.security;


/**
 * Utility class for Spring Security.
 */

import io.quarkus.arc.Arc;
import io.quarkus.security.identity.SecurityIdentity;

public final class SecurityUtils {

    private SecurityUtils() {
    }

    /**
     * @return PK ( ID ) of current user
     */
    public static Long getCurrentUserId() {
        AppUserDetails details = getCurrentUserDetails();
        return (details != null) ? details.getId() : null;
    }

    public static AppUserDetails getCurrentUserDetails() {
        // Programmatically lookup the SecurityIdentity bean from the CDI container
        SecurityIdentity identity = Arc.container().instance(SecurityIdentity.class).get();

        if (identity != null && !identity.isAnonymous()) {
            var principal = identity.getPrincipal();
            if (principal instanceof AppUserDetails details) {
                return details;
            }
        }
        return null;
    }
}
