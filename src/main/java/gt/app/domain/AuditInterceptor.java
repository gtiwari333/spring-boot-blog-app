package gt.app.domain;

import io.quarkus.security.identity.SecurityIdentity;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import org.hibernate.Interceptor;
import org.hibernate.type.Type;

import java.time.Instant;

@ApplicationScoped
public class AuditInterceptor implements Interceptor {

    @Inject
    SecurityIdentity securityIdentity;

    @Override
    public boolean onSave(Object entity, Object id, Object[] state, String[] propertyNames, Type[] types) {
        if (entity instanceof BaseAuditingEntity) {
            Instant now = Instant.now();
            LiteUser currentUser = findCurrentUser();

            // Interceptors in Hibernate 7 still require modifying the state array
            setValue(state, propertyNames, "createdDate", now);
            setValue(state, propertyNames, "lastModifiedDate", now);
            setValue(state, propertyNames, "createdByUser", currentUser);
            setValue(state, propertyNames, "lastModifiedByUser", currentUser);
            return true; // Return true because we modified the state
        }
        return false;
    }

    @Override
    public boolean onFlushDirty(Object entity, Object id, Object[] currentState, Object[] previousState, String[] propertyNames, Type[] types) {
        if (entity instanceof BaseAuditingEntity) {
            setValue(currentState, propertyNames, "lastModifiedDate", Instant.now());
            setValue(currentState, propertyNames, "lastModifiedByUser", findCurrentUser());
            return true;
        }
        return false;
    }

    private void setValue(Object[] state, String[] propertyNames, String propertyToSet, Object value) {
        for (int i = 0; i < propertyNames.length; i++) {
            if (propertyToSet.equals(propertyNames[i])) {
                state[i] = value;
                return;
            }
        }
    }

    private LiteUser findCurrentUser() {
        // If security is enabled, you can resolve the user here
        if (securityIdentity == null || securityIdentity.isAnonymous()) {
            return null;
        }
        // Example: LiteUser user = LiteUser.find("username", securityIdentity.getPrincipal().getName()).firstResult();
        return null;
    }
}
