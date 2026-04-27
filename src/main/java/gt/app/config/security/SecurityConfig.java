package gt.app.config.security;

import gt.app.config.Constants;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.HeadersConfigurer;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;

@EnableWebSecurity
@Configuration
@RequiredArgsConstructor
@EnableMethodSecurity(securedEnabled = true, jsr250Enabled = true)
public class SecurityConfig {

    private static final String[] AUTH_WHITELIST = {
        "/swagger-resources/**",
        "/v3/api-docs/**",
        "/webjars/**",
        "/static/**",
        "/error/**",
        "/swagger-ui/**",
        "/swagger-ui.html/**",
        "/signup/**",
        "/h2-console/**", // enabled for testing/demo purpose
        "/debug/**",
        "/" //landing page is allowed for all
    };

    @Value("${spring.h2.console.enabled:false}")
    private boolean h2ConsoleEnabled;

    @Bean
    protected SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http.headers(h -> h.frameOptions(HeadersConfigurer.FrameOptionsConfig::sameOrigin))
            .authorizeHttpRequests(ah -> {
                ah.requestMatchers(AUTH_WHITELIST).permitAll();
                if (h2ConsoleEnabled) {
                    ah.requestMatchers("/h2-console/**").permitAll();
                }
                ah.requestMatchers("/admin/**").hasAuthority(Constants.ROLE_ADMIN)
                    .requestMatchers("/user/**").hasAuthority(Constants.ROLE_USER)
                    .requestMatchers("/api/**").authenticated()
                    .anyRequest().authenticated();
            })
            .csrf(csrf -> {
                if (h2ConsoleEnabled) {
                    csrf.ignoringRequestMatchers("/h2-console/**");
                }
            })
            .formLogin(f -> f.loginProcessingUrl("/auth/login")
                .permitAll())
            .logout(l -> l.logoutUrl("/auth/logout")
                .logoutSuccessUrl("/?logout")
                .permitAll());

        return http.build();
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

}

