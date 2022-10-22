package gt.app.frwk;

import gt.app.DataCreator;
import gt.app.config.MetadataExtractorIntegrator;
import lombok.RequiredArgsConstructor;
import org.hibernate.boot.Metadata;
import org.hibernate.mapping.Collection;
import org.hibernate.mapping.PersistentClass;
import org.springframework.beans.factory.InitializingBean;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import jakarta.persistence.EntityManager;
import java.util.ArrayList;
import java.util.List;

@Service
@RequiredArgsConstructor
public class TestDataManager implements InitializingBean {
    final EntityManager em;
    final DataCreator dataCreator;

    private final List<String> tableNames = new ArrayList<>(); //shared

    @Override
    public void afterPropertiesSet() {
        Metadata metadata = MetadataExtractorIntegrator.INSTANCE.getMetadata();

        for (Collection persistentClass : metadata.getCollectionBindings()) {
            tableNames.add(persistentClass.getCollectionTable().getExportIdentifier());
        }

        for (PersistentClass persistentClass : metadata.getEntityBindings()) {
            tableNames.add(persistentClass.getTable().getExportIdentifier());
        }

    }

    @Transactional
    public void truncateTablesAndRecreate() {
        truncateTables();
        dataCreator.initData();
    }

    protected void truncateTables() {

        //for H2
        em.createNativeQuery("SET REFERENTIAL_INTEGRITY FALSE").executeUpdate();
        for (String tableName : tableNames) {
            em.createNativeQuery("TRUNCATE TABLE " + tableName).executeUpdate();
        }
        em.createNativeQuery("SET REFERENTIAL_INTEGRITY TRUE").executeUpdate();

//        //for MySQL:
//        em.createNativeQuery("SET @@foreign_key_checks = 0").executeUpdate();
//        for (String tableName : tableNames) {
//            em.createNativeQuery("TRUNCATE TABLE " + tableName).executeUpdate();
//        }
//        em.createNativeQuery("SET @@foreign_key_checks = 1").executeUpdate();

    }


}
