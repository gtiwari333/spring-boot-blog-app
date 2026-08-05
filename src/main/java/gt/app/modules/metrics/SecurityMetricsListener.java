package gt.app.modules.metrics;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.context.event.EventListener;
import org.springframework.security.authentication.event.AbstractAuthenticationFailureEvent;
import org.springframework.security.authentication.event.AuthenticationSuccessEvent;
import org.springframework.security.core.session.SessionDestroyedEvent;
import org.springframework.stereotype.Component;

@Component
public class SecurityMetricsListener {

    private final MeterRegistry meterRegistry;

    public SecurityMetricsListener(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
    }

    @EventListener
    public void onLoginSuccess(AuthenticationSuccessEvent event) {
        // Tagging by login type (e.g., Form, OAuth2) helps slice data cleanly in dashboards
        String authType = event.getAuthentication().getClass().getSimpleName();
        Counter.builder("security.login.success")
            .description("Total number of successful logins")
            .tag("type", authType)
            .register(meterRegistry)
            .increment();
    }

    @EventListener
    public void onLoginFailure(AbstractAuthenticationFailureEvent event) {
        String exceptionType = event.getException().getClass().getSimpleName();
        Counter.builder("security.login.failure")
            .description("Total number of failed login attempts")
            .tag("reason", exceptionType)
            .register(meterRegistry)
            .increment();
    }

}
