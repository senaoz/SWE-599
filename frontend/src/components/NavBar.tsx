import { useLocation, useNavigate } from "react-router-dom";
import { LogOut01, Moon01, CloudSun01 } from "@untitledui/icons";
import { HeaderNavigationBase } from "@/components/application/app-navigation/header-navigation";
import { Button } from "@/components/base/buttons/button";
import { useDarkMode } from "../hooks/useDarkMode";
import { useMe } from "../hooks/useMe";

interface NavBarProps {
  onLogout: () => void;
}

const navItems = [
  { label: "For me", href: "/" },
  { label: "Explore", href: "/explore" },
  { label: "Researchers", href: "/researchers" },
  { label: "Institutions", href: "/institutions" },
];

export default function NavBar({ onLogout }: NavBarProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { dark, toggle } = useDarkMode();
  const { me } = useMe();
  const isAdmin = !!me?.is_admin;

  const handleLogout = () => {
    onLogout();
    navigate("/login");
  };

  return (
    <HeaderNavigationBase
      activeUrl={location.pathname}
      items={isAdmin ? [...navItems, { label: "Admin", href: "/admin" }] : navItems}
      actions={
        <div className="flex items-center gap-2">
          <Button
            color="tertiary"
            size="sm"
            iconLeading={dark ? CloudSun01 : Moon01}
            onClick={toggle}
          />
          <Button
            color="secondary"
            size="sm"
            iconLeading={LogOut01}
            onClick={handleLogout}
          >
            Logout
          </Button>
        </div>
      }
    />
  );
}
