import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ErrorMessageProps {
title?: string;
message: string;
onRetry?: () => void;
}

export function ErrorMessage({
title = "Erro",
message,
onRetry
}: ErrorMessageProps) {
return (
<Alert variant="destructive" className="my-4">
<AlertCircle className="h-4 w-4" />
<AlertTitle>{title}</AlertTitle>
<AlertDescription className="mt-2">
{message}
{onRetry && (
<Button 
            variant="outline" 
            size="sm" 
            className="mt-2"
            onClick={onRetry}
          >
Tentar Novamente
</Button>
)}
</AlertDescription>
</Alert>
);
}
