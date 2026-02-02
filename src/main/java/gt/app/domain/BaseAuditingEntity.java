package gt.app.domain;

import com.fasterxml.jackson.annotation.JsonIgnore;
import lombok.Getter;
import lombok.Setter;

import jakarta.persistence.*;

import java.time.Instant;

@MappedSuperclass
@Getter
@Setter
abstract class BaseAuditingEntity extends BaseEntity {

    private static final long serialVersionUID = 4681401402666658611L;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "created_by_user_id", updatable = false, nullable = false)
    @JsonIgnore//ignore completely to avoid StackOverflow exception by User.createdByUser logic, use DTO
    private LiteUser createdByUser;

    @Column(name = "created_date", updatable = false, nullable = false)
    private Instant createdDate;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "last_modified_by_user_id")
    @JsonIgnore//ignore completely to avoid StackOverflow exception by User.lastModifiedByUser logic, use DTO
    private LiteUser lastModifiedByUser;

    @Column(name = "last_modified_date")
    private Instant lastModifiedDate;
}
