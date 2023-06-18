package gt.app.config.security;

import gt.app.config.Constants;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.annotation.web.configurers.HeadersConfigurer;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;

@EnableWebSecurity
@Configuration
@RequiredArgsConstructor
public class SecurityConfig {

    private static final String[] AUTH_WHITELIST = {
        "/swagger-resources/**",
        "/v3/api-docs/**",
        "/h2-console/**",
        "/webjars/**",
        "/static/**",
        "/error/**",
        "/swagger-ui/**",
        "/swagger-ui.html/**",
        "/signup/**",
        "/" //landing page is allowed for all
    };

    @Bean
    protected SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http.headers(h -> h.frameOptions(HeadersConfigurer.FrameOptionsConfig::sameOrigin))
            .authorizeHttpRequests(ah -> ah.requestMatchers(AUTH_WHITELIST).permitAll()
                .requestMatchers("/admin/**").hasAuthority(Constants.ROLE_ADMIN)
                .requestMatchers("/user/**").hasAuthority(Constants.ROLE_USER)
                .requestMatchers("/api/**").authenticated()//individual api will be secured differently
                .anyRequest().authenticated())
            .csrf(AbstractHttpConfigurer::disable)
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

