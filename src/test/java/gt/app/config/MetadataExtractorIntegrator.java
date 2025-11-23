package gt.app.config;

import lombok.Data;
import org.hibernate.boot.Metadata;
import org.hibernate.boot.model.relational.Database;
import org.hibernate.boot.spi.BootstrapContext;
import org.hibernate.cache.internal.CollectionCacheInvalidator;
import org.hibernate.engine.spi.SessionFactoryImplementor;
import org.hibernate.integrator.spi.Integrator;
import org.hibernate.service.spi.SessionFactoryServiceRegistry;

@Data
public class MetadataExtractorIntegrator implements Integrator {

    public static final MetadataExtractorIntegrator INSTANCE =
                            new MetadataExtractorIntegrator();
    private Database database;
    private Metadata metadata;

    @Override
    public void integrate(Metadata metadata,
                          BootstrapContext bootstrapContext,
                          SessionFactoryImplementor sessionFactory) {
        this.database = metadata.getDatabase();
        this.metadata = metadata;
    }

    @Override
    public void disintegrate(SessionFactoryImplementor sf,
                             SessionFactoryServiceRegistry sr) {
    }
}
