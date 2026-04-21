-- SQL script to set up customer manager role for testing the approval workflow
-- This inserts the module config and assigns a customer manager role to a user

-- First, verify the delivery_orders module exists and get its ID
DECLARE @module_id INT;
SELECT @module_id = id FROM Intra_Admin_ModuleConfig WHERE module_key = 'delivery_orders';

IF @module_id IS NOT NULL
BEGIN
    PRINT 'Delivery Orders module ID: ' + CAST(@module_id AS VARCHAR(10));

    -- For testing, we need to know the emp_id of the current user
    -- You can replace this with the actual emp_id
    -- For now, let's find employees who have already created orders

    SELECT TOP 5
        Created_by as emp_id,
        COUNT(*) as order_count
    FROM Intra_SalesOrder
    WHERE Created_by IS NOT NULL
    GROUP BY Created_by
    ORDER BY order_count DESC;

    -- Example: Assign the do_customer_manager role to employees
    -- Replace @EMP_ID with actual employee ID from above
    DECLARE @EMP_ID INT = 1001; -- Default test employee

    -- Check if already assigned
    IF NOT EXISTS (
        SELECT 1 FROM Intra_Admin_UserModuleRole
        WHERE module_id = @module_id AND emp_id = @EMP_ID AND role_key = 'do_customer_manager'
    )
    BEGIN
        INSERT INTO Intra_Admin_UserModuleRole (module_id, emp_id, role_key, assigned_by, assigned_at)
        VALUES (@module_id, @EMP_ID, 'do_customer_manager', 1, GETDATE());
        PRINT 'Assigned do_customer_manager role to emp_id: ' + CAST(@EMP_ID AS VARCHAR(10));
    END
    ELSE
    BEGIN
        PRINT 'Role already assigned to emp_id: ' + CAST(@EMP_ID AS VARCHAR(10));
    END
END
ELSE
BEGIN
    PRINT 'Delivery Orders module not found!';
    PRINT 'Available modules:';
    SELECT id, module_key FROM Intra_Admin_ModuleConfig;
END
