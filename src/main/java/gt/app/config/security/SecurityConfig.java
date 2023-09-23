package gt.app.config.security;

import gt.app.config.Constants;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.annotation.web.configurers.HeadersConfigurer;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.servlet.util.matcher.MvcRequestMatcher;
import org.springframework.security.web.util.matcher.AntPathRequestMatcher;
import org.springframework.web.servlet.handler.HandlerMappingIntrospector;

import java.util.stream.Stream;

import static org.springframework.security.web.util.matcher.AntPathRequestMatcher.antMatcher;

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
        "/" //landing page is allowed for all
    };


    @Bean
    protected SecurityFilterChain filterChain(HttpSecurity http, HandlerMappingIntrospector introspector) throws Exception {
        var mvcH2Console = new MvcRequestMatcher.Builder(introspector).servletPath("/h2-console");
        http.headers(h -> h.frameOptions(HeadersConfigurer.FrameOptionsConfig::sameOrigin))
            .authorizeHttpRequests(ah -> ah
                .requestMatchers(Stream.of(AUTH_WHITELIST).map(AntPathRequestMatcher::antMatcher).toList().toArray(new AntPathRequestMatcher[0])).permitAll()
                .requestMatchers(mvcH2Console.pattern("/**")).permitAll()
                .requestMatchers(antMatcher("/admin/**")).hasAuthority(Constants.ROLE_ADMIN)
                .requestMatchers(antMatcher("/user/**")).hasAuthority(Constants.ROLE_USER)
                .requestMatchers(antMatcher("/api/**")).authenticated()//individual api will be secured differently
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

