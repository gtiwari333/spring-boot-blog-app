package gt.app.config;

import org.springframework.boot.webmvc.autoconfigure.DispatcherServletAutoConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.context.WebApplicationContext;
import org.springframework.web.servlet.DispatcherServlet;
import org.springframework.web.servlet.HandlerMapping;
import org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerMapping;

@Configuration
class DispatcherServletConfig {

    // disable these for pure REST api

//    @Bean
//    public HandlerMapping handlerMapping() {
//        var mapping = new RequestMappingHandlerMapping();
//        return mapping;
//    }

//    @Bean(name = DispatcherServletAutoConfiguration.DEFAULT_DISPATCHER_SERVLET_BEAN_NAME)
//    public DispatcherServlet dispatcherServlet(WebApplicationContext context) {
//        var dispatcherServlet = new DispatcherServlet(context);
//        dispatcherServlet.setDetectAllHandlerMappings(false);
//        return dispatcherServlet;
//    }

}
