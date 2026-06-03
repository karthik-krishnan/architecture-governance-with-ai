package com.example.restaurant.order;

import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;
import com.tngtech.archunit.library.dependencies.SliceRule;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices;

@AnalyzeClasses(
        packages = "com.example.restaurant.order",
        importOptions = ImportOption.DoNotIncludeTests.class
)
public class ArchitectureFitnessFunctionsTest {

    // ─── FITNESS FUNCTION 1 ───────────────────────────────────────────────────
    // Controllers must not access repositories directly.
    // They must go through the application (service) layer.
    @ArchTest
    static final ArchRule controllers_should_not_directly_access_repositories =
            noClasses()
                    .that().resideInAPackage("..controller..")
                    .should().accessClassesThat().resideInAPackage("..repository..")
                    .because("Controllers must go through the application layer — direct repository access " +
                             "bypasses business-logic enforcement and makes the boundary unenforceable");

    // ─── FITNESS FUNCTION 2 ───────────────────────────────────────────────────
    // Domain model must not depend on infrastructure.
    // Infrastructure details (HTTP clients, DB adapters) must never leak into business logic.
    @ArchTest
    static final ArchRule domain_should_not_depend_on_infrastructure =
            noClasses()
                    .that().resideInAPackage("..domain..")
                    .should().dependOnClassesThat().resideInAPackage("..infrastructure..")
                    .because("Domain model must stay pure — coupling it to infrastructure makes " +
                             "business logic impossible to unit-test without spinning up external systems");

    // ─── FITNESS FUNCTION 3 ───────────────────────────────────────────────────
    // Application services must not depend directly on external client implementations.
    // They must depend on abstractions (interfaces defined in application or domain).
    @ArchTest
    static final ArchRule application_should_not_directly_use_infrastructure_clients =
            noClasses()
                    .that().resideInAPackage("..application..")
                    .should().dependOnClassesThat().resideInAPackage("..infrastructure..")
                    .because("Application services must depend on abstractions, not concrete infrastructure. " +
                             "Concrete clients belong in infrastructure; interfaces belong in application or domain");

    // ─── FITNESS FUNCTION 4 ───────────────────────────────────────────────────
    // No cyclic dependencies between architectural layers.
    // If domain → application and application → domain, neither can be understood in isolation.
    @ArchTest
    static final SliceRule no_cyclic_dependencies_between_layers =
            slices()
                    .matching("com.example.restaurant.order.(*)..")
                    .should().beFreeOfCycles()
                    .because("Cyclic layer dependencies make the codebase impossible to reason about, " +
                             "test in isolation, or deploy independently");

    // ─── FITNESS FUNCTION 5 ───────────────────────────────────────────────────
    // Repository classes may only be accessed from the application or infrastructure layer.
    // Controllers, domain, and other packages must not reach into the repository directly.
    @ArchTest
    static final ArchRule repositories_only_accessible_from_application_or_infrastructure =
            noClasses()
                    .that().resideOutsideOfPackages(
                            "com.example.restaurant.order.application",
                            "com.example.restaurant.order.infrastructure",
                            "com.example.restaurant.order.repository"
                    )
                    .should().accessClassesThat().resideInAPackage("..repository..")
                    .because("Uncontrolled repository access from controllers or domain objects " +
                             "turns every layer into a data-access layer and destroys the service boundary");
}
