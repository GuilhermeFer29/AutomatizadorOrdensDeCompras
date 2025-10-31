import { LayoutDashboard, Bot, ShoppingCart, Package, LogOut } from "lucide-react";
import { NavLink, useNavigate } from "react-router-dom";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Chat com Agentes", href: "/agents", icon: Bot },
  { name: "Ordens de Compra", href: "/orders", icon: ShoppingCart },
  { name: "Catálogo", href: "/catalog", icon: Package },
];

export function Sidebar() {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem("token");
    navigate("/login");
  };

  return (
    <aside className="w-64 bg-card border-r border-border min-h-screen flex flex-col">
      <div className="p-6">
        <h1 className="text-xl font-semibold text-foreground">
          Sistema de Automação
        </h1>
        <p className="text-xs text-muted-foreground mt-1">
          Ordens Inteligentes
        </p>
      </div>

      <nav className="px-3 space-y-1 flex-1">
        {navigation.map((item) => (
          <NavLink
            key={item.name}
            to={item.href}
            end={item.href === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-secondary hover:text-foreground"
              )
            }
          >
            <item.icon className="h-5 w-5" />
            {item.name}
          </NavLink>
        ))}
      </nav>

      <div className="p-3 border-t border-border">
        <Button
          variant="destructive"
          className="w-full flex items-center gap-2"
          onClick={handleLogout}
        >
          <LogOut className="h-4 w-4" />
          Sair
        </Button>
      </div>
    </aside>
  );
}
