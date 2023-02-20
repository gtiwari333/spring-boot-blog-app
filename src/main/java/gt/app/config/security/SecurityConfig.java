package gt.app.config.security;

import gt.app.config.Constants;
import gt.app.modules.user.AppUserDetailsService;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.authentication.builders.AuthenticationManagerBuilder;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
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
        "/swagger-ui/**",
        "/swagger-ui.html/**",
        "/wro4j/**",
        "/" //landing page is allowed for all
    };

//    private final AppUserDetailsService appUserDetailsService;
//
//    @Autowired
//    public void configureGlobal(AuthenticationManagerBuilder authenticationManagerBuilder) throws Exception {
//        authenticationManagerBuilder
//            .userDetailsService(appUserDetailsService)
//            .passwordEncoder(passwordEncoder());
//    }

    @Bean
    SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .headers().frameOptions().sameOrigin()
            .and()
                .authorizeHttpRequests()
                .requestMatchers(AUTH_WHITELIST).permitAll()
                .requestMatchers("/admin/**").hasAuthority(Constants.ROLE_ADMIN)
                .requestMatchers("/user/**").hasAuthority(Constants.ROLE_USER)
                .requestMatchers("/api/**").authenticated()//individual api will be secured differently
                .anyRequest().authenticated() //this one will catch the rest patterns
            .and()
                .csrf().disable()
            .formLogin()
                .loginProcessingUrl("/auth/login")
                .permitAll()
            .and()
                .logout()
                .logoutUrl("/auth/logout")
                .logoutSuccessUrl("/?logout")
                .permitAll();
        return http.build();

    }

    @Bean
    PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

}

