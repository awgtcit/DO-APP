$server = "172.50.35.75"
$database = "mtcintranet1"
$username = "sa"
$password = "Admin@123"

Write-Host "Setting up Customer Manager role for delivery orders..."

$connectionString = "Server=$server;Database=$database;User Id=$username;Password=$password;Connection Timeout=30;TrustServerCertificate=Yes;"

$connection = New-Object System.Data.SqlClient.SqlConnection
$connection.ConnectionString = $connectionString

try {
    $connection.Open()
    Write-Host "Connected to $server\$database"

    # Get the delivery_orders module ID
    $query = "SELECT id FROM Intra_Admin_ModuleConfig WHERE module_key = 'delivery_orders'"
    $command = New-Object System.Data.SqlClient.SqlCommand($query, $connection)
    $moduleId = $command.ExecuteScalar()

    if ($moduleId) {
        Write-Host "Found delivery_orders module (ID: $moduleId)"

        # Find an employee who created orders
        $empQuery = "SELECT TOP 1 Created_by FROM Intra_SalesOrder WHERE Created_by IS NOT NULL ORDER BY ID DESC"
        $command = New-Object System.Data.SqlClient.SqlCommand($empQuery, $connection)
        $empId = $command.ExecuteScalar()

        if ($empId) {
            Write-Host "Found employee $empId"

            # Assign the customer manager role
            $insertQuery = "INSERT INTO Intra_Admin_UserModuleRole (module_id, emp_id, role_key, assigned_by, assigned_at) SELECT @moduleId, @empId, 'do_customer_manager', 1, GETDATE() WHERE NOT EXISTS (SELECT 1 FROM Intra_Admin_UserModuleRole WHERE module_id = @moduleId AND emp_id = @empId AND role_key = 'do_customer_manager')"

            $command = New-Object System.Data.SqlClient.SqlCommand($insertQuery, $connection)
            $command.Parameters.AddWithValue("@moduleId", $moduleId)
            $command.Parameters.AddWithValue("@empId", $empId)

            $rowsAffected = $command.ExecuteNonQuery()
            Write-Host "Assigned do_customer_manager role to employee $empId"
            Write-Host ""
            Write-Host "SUCCESS: The user with emp_id=$empId now has the Customer Manager role."
            Write-Host "They should see the 'Approve' button when viewing orders in PENDING CUSTOMER APPROVAL status."
        }
        else {
            Write-Host "ERROR: No employees found"
        }
    }
    else {
        Write-Host "ERROR: Delivery Orders module not found!"
    }

}
catch {
    Write-Host "ERROR: $_"
}
finally {
    $connection.Close()
    $connection.Dispose()
}
