package gt.app.config.security;

import org.springframework.security.authentication.AnonymousAuthenticationToken;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;

import java.util.HashSet;
import java.util.Optional;

/**
 * Utility class for Spring Security.
 */
public final class SecurityUtils {

    private SecurityUtils() {
    }

    /**
     * Get the login of the current user.
     *
     * @return the login of the current user
     */
    public static Optional<String> getCurrentUserLogin() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        return Optional.ofNullable(authentication)
            .map(a -> {
                if (a.getPrincipal() instanceof User) {
                    User springSecurityUser = (User) a.getPrincipal();
                    return springSecurityUser.getUsername();
                } else if (a.getPrincipal() instanceof String) {
                    return (String) a.getPrincipal();
                }
                return null;
            });
    }

    /**
     * @return PK ( ID ) of current id
     */
    public static Long getCurrentUserId() {

        User user = getCurrentUserDetails();
        if (user instanceof AppUserDetails) {
            AppUserDetails appUserDetails = (AppUserDetails) user;
            return appUserDetails.getId();
        }
        return null;
    }

    public static User getCurrentUserDetails() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        return getCurrentUserDetails(authentication);
    }

    public static User getCurrentUserDetails(Authentication authentication) {
        User userDetails = null;
        if (authentication != null && authentication.getPrincipal() instanceof User) {
            userDetails = (User) authentication.getPrincipal();
        }
        return userDetails;
    }


    public static boolean isAuthenticated() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        return !(authentication == null || authentication instanceof AnonymousAuthenticationToken);
    }

    public static boolean isCurrentUserHasRole(String authority) {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        return authentication != null && authentication.getAuthorities().stream().anyMatch(grantedAuthority -> grantedAuthority.getAuthority().equals(authority));
    }

    public static void setCurrentUserWithToken(UserDetails user) {
        SecurityContext securityContext = SecurityContextHolder.createEmptyContext();

        UsernamePasswordAuthenticationToken authentication = new UsernamePasswordAuthenticationToken(user,
            "token", //this can be empty
            new HashSet<>(user.getAuthorities()) //use type
        );

        securityContext.setAuthentication(authentication);

        SecurityContextHolder.setContext(securityContext);
    }
}
