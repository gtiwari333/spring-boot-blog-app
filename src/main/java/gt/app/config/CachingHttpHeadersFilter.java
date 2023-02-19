package gt.app.config;

import org.springframework.web.filter.OncePerRequestFilter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.concurrent.TimeUnit;

class CachingHttpHeadersFilter extends OncePerRequestFilter {

    final long lastModified = System.currentTimeMillis();
    final long cacheTimeToLive = TimeUnit.DAYS.toMillis(1461L);

    @Override
    public void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
        throws IOException, ServletException {

        response.setHeader("Cache-Control", "max-age=" + cacheTimeToLive + ", public");
        response.setHeader("Pragma", "cache");

        // Setting Expires header, for proxy caching
        response.setDateHeader("Expires", cacheTimeToLive + System.currentTimeMillis());

        // Setting the Last-Modified header, for browser caching
        response.setDateHeader("Last-Modified", lastModified);

        filterChain.doFilter(request, response);
    }
}
