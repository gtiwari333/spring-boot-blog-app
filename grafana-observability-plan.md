# Grafana Observability Stack — Learning & Setup Plan

## Context

This Spring Boot blog app (SB 4.0.6, Java 21) already has `spring-boot-starter-actuator` on the classpath but **no metrics registry**, **no `management.*` config**, and actuator endpoints are **not whitelisted** in `SecurityConfig.java` — they fall through to `.anyRequest().authenticated()`. The existing `docker-compose.yml` only runs MailHog.

Goal: build a full Grafana-based observability stack for hands-on learning, with multiple app instances to see aggregation in action.

---

## Architecture

```
 Browser                     Browser                     Browser
:3000 (Grafana)             :9090 (Prometheus)         :8080/:8081 (App instances)

┌──────────────────────────────────────────────────────────────┐
│                    Grafana :3000                               │
│  Datasource → Prometheus                                      │
│  Dashboards: JVM Micrometer | HTTP Spring | Business Blog     │
│  Alerting → can be added later                                │
└─────────────────────┬────────────────────────────────────────┘
                      │ PromQL queries
┌─────────────────────▼────────────────────────────────────────┐
│                  Prometheus :9090                              │
│  scrape_interval: 15s                                         │
│  targets: blog-app-1:8080, blog-app-2:8080                    │
└──────┬──────────────────────┬────────────────────────────────┘
       │ GET /actuator/prometheus (every 15s)
┌──────▼──────┐       ┌───────▼──────┐
│ blog-app-1  │       │ blog-app-2   │
│ :8080       │       │ :8081        │
│ H2 (mem)    │       │ H2 (mem)     │
│ Micrometer  │       │ Micrometer   │
│ + Prometheus│       │ + Prometheus │
│ registry    │       │ registry     │
└─────────────┘       └──────────────┘
      │                       │
      └─────── MailHog ───────┘
              :1025 (SMTP)
              :8025 (Web UI)
```

All services orchestrated by a single `docker compose up`.

---

## Implementation Phases

### Phase 1: Add Micrometer → Prometheus bridge

**File: `pom.xml`** (add after the actuator dependency, around line 113)

```xml
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-registry-prometheus</artifactId>
</dependency>
```

This single dependency auto-configures a `/actuator/prometheus` endpoint that emits all Micrometer metrics in Prometheus text format. No other code changes needed — Spring Boot auto-config handles the rest.

### Phase 2: Expose management endpoints + permit in security

**File: `src/main/resources/application.yml`** (append at end)

```yaml
management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
  endpoint:
    health:
      show-details: always
  metrics:
    tags:
      application: ${spring.application.name}
```

**File: `SecurityConfig.java`** (line 22, add to `AUTH_WHITELIST` array)

Add `"/actuator/**"` to the existing whitelist so Prometheus can scrape without auth:

```java
private static final String[] AUTH_WHITELIST = {
    "/swagger-resources/**",
    "/v3/api-docs/**",
    "/webjars/**",
    "/static/**",
    "/error/**",
    "/swagger-ui/**",
    "/swagger-ui.html/**",
    "/signup/**",
    "/h2-console/**",
    "/debug/**",
    "/actuator/**",   // ← ADD: Prometheus scraping
    "/"
};
```

Also add CSRF ignoring for actuator:

```java
.csrf(csrf -> {
    if (h2ConsoleEnabled) {
        csrf.ignoringRequestMatchers("/h2-console/**");
    }
    csrf.ignoringRequestMatchers("/actuator/**");  // ← ADD
})
```

### Phase 3: Create docker profile

**New file: `src/main/resources/application-docker.yml`**

```yaml
spring:
  datasource:
    url: jdbc:h2:mem:testdb
  h2:
    console:
      enabled: true
  thymeleaf:
    cache: true  # cached in docker, unlike dev
```

This mirrors dev profile settings needed for H2 + H2 console. The existing `Constants.java` already defines `SPRING_PROFILE_DOCKER = "docker"` — this config completes it.

Also need to update `HelloResource.java` to include the `docker` profile so `/debug/**` endpoints work:

```java
@Profile({Constants.SPRING_PROFILE_DEVELOPMENT, Constants.SPRING_PROFILE_TEST, Constants.SPRING_PROFILE_DOCKER})
```

### Phase 4: Prometheus configuration

**New file: `docker/prometheus/prometheus.yml`**

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'blog-app'
    metrics_path: '/actuator/prometheus'
    static_configs:
      - targets:
          - 'blog-app-1:8080'
          - 'blog-app-2:8080'
```

### Phase 5: Grafana provisioning

**New file: `docker/grafana/datasources/prometheus.yml`**

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

**New file: `docker/grafana/dashboards/dashboard.yml`**

```yaml
apiVersion: 1
providers:
  - name: 'default'
    folder: ''
    type: file
    options:
      path: /etc/grafana/provisioning/dashboards
```

**New files: 3 pre-built dashboards** under `docker/grafana/dashboards/`:

| Dashboard | What it shows |
|-----------|--------------|
| `jvm-micrometer.json` | Heap/non-heap, GC pauses & count, threads live/daemon/peak, CPU usage, class loading, memory pools |
| `http-spring.json` | Request rate (RPS), error rate 4xx/5xx, latency p50/p90/p99, top endpoints by traffic |
| `business-blog.json` | Note CRUD operations rate, user signups, file uploads, active user sessions |

Dashboards will use Grafana variables (`$instance`) to filter/split by app instance automatically.

### Phase 6: Docker Compose — full stack

**File: `docker-compose.yml`** (rewrite)

```yaml
services:
  # --- Application instances (2 for multi-instance learning) ---
  blog-app-1:
    build: .
    ports:
      - "8080:8080"
    environment:
      - SPRING_PROFILES_ACTIVE=docker
    networks:
      - monitoring

  blog-app-2:
    build: .
    ports:
      - "8081:8080"
    environment:
      - SPRING_PROFILES_ACTIVE=docker
    networks:
      - monitoring

  # --- Mail testing ---
  mailhog:
    image: mailhog/mailhog
    ports:
      - "1025:1025"
      - "8025:8025"
    networks:
      - monitoring

  # --- Observability ---
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./docker/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    ports:
      - "9090:9090"
    networks:
      - monitoring

  grafana:
    image: grafana/grafana:latest
    volumes:
      - ./docker/grafana/datasources:/etc/grafana/provisioning/datasources
      - ./docker/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - grafana_data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_INSTALL_PLUGINS=grafana-clock-panel,grafana-piechart-panel
    ports:
      - "3000:3000"
    networks:
      - monitoring

volumes:
  prometheus_data:
  grafana_data:

networks:
  monitoring:
    driver: bridge
```

---

## Learning Path (hands-on exercises in order)

| # | Exercise | What to do | What you'll learn |
|---|----------|-----------|-------------------|
| 1 | **Bring it all up** | `docker compose up --build` | How 5+ services wire together; Docker networking |
| 2 | **Verify metrics** | `curl localhost:8080/actuator/prometheus` | Raw Prometheus metrics format (counters, gauges, histograms) |
| 3 | **Verify Prometheus** | Open `:9090/targets` — both instances UP | Prometheus service discovery, target health |
| 4 | **Explore Grafana** | Open `:3000` (admin/admin), browse pre-built dashboards | Grafana UI: panels, rows, time picker, refresh intervals |
| 5 | **Generate traffic** | Browse blog, create/delete notes, upload files, trigger errors | See metrics move in real time across dashboards |
| 6 | **Instance filtering** | Use the `$instance` variable dropdown in dashboards | Grafana template variables — filter by app instance |
| 7 | **Edit a dashboard** | Add a new panel: `rate(http_server_requests_seconds_count[1m])` | PromQL basics: `rate()`, label filters, time ranges |
| 8 | **Create dashboard from scratch** | Build a "Notes API" dashboard with: stat tiles (total notes), time series (creates/min), table (latest notes) | Dashboard design: stat, time series, table panels |
| 9 | **Explore PromQL** | Try queries: `histogram_quantile(0.99, rate(...))`, `sum by(status)(...)`, `increase(...[5m])` | PromQL functions: quantiles, aggregations, ranges |
| 10 | **Scale experiment** | Stop one instance (`docker compose stop blog-app-2`), watch dashboards | HA visibility — metrics drop for one instance but the other continues |
| 11 | **Add a 3rd instance** | Copy-paste `blog-app-3` in docker-compose, add to Prometheus targets, restart | Horizontal scaling — adding instances is configuration, not code |
| 12 | **Set up an alert** | Grafana alert: error rate > 5% for 5min → notification | Grafana alerting: conditions, evaluation intervals, notification channels |
| 13 | **Custom metric (Java)** | Add `meterRegistry.counter("blog.notes.created").increment()` in `NoteController` | Micrometer API: Counter, Timer, Gauge, DistributionSummary |

---

## Key Concepts You'll Learn

### Grafana-specific
- **Data Sources**: Prometheus, but also SQL, Elasticsearch, Loki, etc. — unified query interface
- **Panels**: stat, time series, table, gauge, bar gauge, heatmap, pie chart, geomap
- **Variables**: `$instance`, `$endpoint`, `$method` — dashboard-wide or panel-specific filters
- **Transformations**: Merge, filter by value, group by, calculate field, reduce, sort
- **Alerting**: Multi-dimensional alert rules, evaluation groups, notification policies

### Prometheus/Micrometer
- **Counter**: Monotonically increasing count (requests, errors)
- **Gauge**: Up/down value (memory, threads, queue size)
- **Timer/Summary**: Latency distribution with quantiles
- **Histogram**: Latency buckets for PromQL `histogram_quantile()`
- **Tags/labels**: `application`, `instance`, `method`, `uri`, `status`, `outcome`

### JVM metrics (auto-collected by Micrometer)
- `jvm_memory_used_bytes` / `jvm_memory_max_bytes` — heap & non-heap
- `jvm_gc_pause_seconds_count` / `_sum` — GC frequency & duration
- `jvm_threads_live_threads` / `daemon_threads` / `peak_threads`
- `jvm_classes_loaded_classes`
- `process_cpu_usage` / `system_cpu_usage`
- `jvm_buffer_total_capacity_bytes` / `jvm_buffer_count_buffers`

---

## Files Summary

### New files to create (9)
```
docker/prometheus/prometheus.yml
docker/grafana/datasources/prometheus.yml
docker/grafana/dashboards/dashboard.yml
docker/grafana/dashboards/jvm-micrometer.json
docker/grafana/dashboards/http-spring.json
docker/grafana/dashboards/business-blog.json
src/main/resources/application-docker.yml
```

### Files to modify (4)
```
pom.xml                        ← add micrometer-registry-prometheus
application.yml                ← add management.* block
SecurityConfig.java            ← whitelist /actuator/**, add CSRF ignore
HelloResource.java             ← add SPRING_PROFILE_DOCKER to @Profile
docker-compose.yml             ← add blog-app-1, blog-app-2, prometheus, grafana
```

---

## Verification

1. `docker compose up --build` — 5 containers start (2× app, mailhog, prometheus, grafana)
2. `curl http://localhost:8080/actuator/prometheus | head -20` — Prometheus metrics output
3. `curl http://localhost:8081/actuator/prometheus | head -20` — second instance also working
4. Open `http://localhost:9090/targets` — both `blog-app:8080` targets state = UP
5. Open `http://localhost:3000` (admin/admin) → Dashboards → JVM Micrometer → data populating
6. Browse `http://localhost:8080` — sign up, create notes, upload files
7. HTTP dashboard shows request rate, latency percentiles
8. `docker compose stop blog-app-2` → dashboards show only 1 instance
9. `docker compose start blog-app-2` → both instances back in dashboards
