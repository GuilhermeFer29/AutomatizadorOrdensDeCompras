import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/types/api.types";

interface AlertsTableProps {
  alerts: Alert[];
}

const severityStyles = {
  success: "bg-success/10 text-success hover:bg-success/20",
  warning: "bg-warning/10 text-warning hover:bg-warning/20",
  error: "bg-destructive/10 text-destructive hover:bg-destructive/20",
};

export function AlertsTable({ alerts }: AlertsTableProps) {
  return (
    <Card className="shadow-sm">
      <CardHeader>
        <CardTitle>Produtos em Alerta</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Produto</TableHead>
              <TableHead>Alerta</TableHead>
              <TableHead className="text-right">Estoque Atual</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {alerts.map((alert) => (
              <TableRow key={alert.id}>
                <TableCell className="font-medium">{alert.product}</TableCell>
                <TableCell>
                  <Badge className={severityStyles[alert.severity]} variant="secondary">
                    {alert.alert}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">{alert.stock} unidades</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
