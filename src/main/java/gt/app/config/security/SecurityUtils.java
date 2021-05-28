package gt.app.config.security;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.User;

/**
 * Utility class for Spring Security.
 */
public final class SecurityUtils {

    private SecurityUtils() {
    }

    /**
     * @return PK ( ID ) of current id
     */
    public static Long getCurrentUserId() {

        User user = getCurrentUserDetails();
        if (user instanceof AppUserDetails appUserDetails) {
            return appUserDetails.getId();
        }
        return null;
    }

    public static User getCurrentUserDetails() {
        var authentication = SecurityContextHolder.getContext().getAuthentication();
        return getCurrentUserDetails(authentication);
    }

    public static User getCurrentUserDetails(Authentication authentication) {
        User userDetails = null;
        if (authentication != null && authentication.getPrincipal() instanceof User) {
            userDetails = (User) authentication.getPrincipal();
        }
        return userDetails;
    }
}
